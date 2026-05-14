import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class NotificationController {
  static final FlutterLocalNotificationsPlugin _localNotificationsPlugin =
      FlutterLocalNotificationsPlugin();

  static const String _apiBaseUrl = 'https://api.magicsmile.kz';
  static const String _frontendUrl = 'https://magicsmile.kz';

  // Cached auth info
  static String? _authToken;
  static String? _authType; // 'BEARER', 'PATIENT', 'PARENT'
  static InAppWebViewController? _webViewController;
  static bool _isWaitingForApnsToken = false;
  static bool _fcmTokenSent = false;
  static bool _fetchInterceptorInjected = false;

  static Future<void> initialize() async {
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings();
    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );
    await _localNotificationsPlugin.initialize(
      settings,
      onDidReceiveNotificationResponse: (response) {
        if (response.payload != null) {
          final data = jsonDecode(response.payload!);
          if (_webViewController != null && data['url'] != null) {
            String targetUrl = data['url'];
            if (!targetUrl.startsWith('http')) {
              targetUrl = '$_frontendUrl$targetUrl';
            }
            _webViewController!.loadUrl(
              urlRequest: URLRequest(url: WebUri(targetUrl)),
            );
          }
        }
      },
    );

    // Восстановить сохранённый auth из SharedPreferences
    final prefs = await SharedPreferences.getInstance();
    _authToken = prefs.getString('auth_token');
    _authType = prefs.getString('auth_type');

    final authTimestamp = prefs.getInt('auth_timestamp') ?? 0;
    final currentTime = DateTime.now().millisecondsSinceEpoch;
    if (currentTime - authTimestamp > 24 * 60 * 60 * 1000) {
      _authToken = null;
      _authType = null;
      await prefs.remove('auth_token');
      await prefs.remove('auth_type');
      await prefs.remove('auth_timestamp');
    }

    if (_authToken != null) {
      debugPrint('FCM: Restored cached auth ($_authType)');
    }
  }

  static Future<String> _getDeviceId() async {
    final deviceInfo = DeviceInfoPlugin();
    if (kIsWeb) return 'web_device';
    if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      return androidInfo.id;
    } else if (Platform.isIOS) {
      final iosInfo = await deviceInfo.iosInfo;
      return iosInfo.identifierForVendor ?? 'unknown_ios_device';
    }
    return 'unknown_device';
  }

  static String _getDeviceType() {
    if (kIsWeb) return 'web';
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'apple';
    return 'unknown';
  }

  static Future<bool> _waitForApnsToken({int maxAttempts = 10, Duration delay = const Duration(seconds: 1)}) async {
    if (!Platform.isIOS) return true;
    for (int i = 0; i < maxAttempts; i++) {
      try {
        final apnsToken = await FirebaseMessaging.instance.getAPNSToken();
        if (apnsToken != null) return true;
        await Future.delayed(delay);
      } catch (_) {}
    }
    return false;
  }

  /// JavaScript-код который перехватывает все fetch-запросы к API логина
  /// и автоматически передаёт JWT токен во Flutter через handler
  static String get _fetchInterceptorJs => """
    (function() {
      if (window.__fcmInterceptorInstalled) return;
      window.__fcmInterceptorInstalled = true;

      // URL-паттерны эндпоинтов логина
      var loginEndpoints = [
        '/api/game/auth/parent-login/',
        '/api/game/auth/qr-login/',
        '/api/login/'
      ];

      function isLoginUrl(url) {
        for (var i = 0; i < loginEndpoints.length; i++) {
          if (url.indexOf(loginEndpoints[i]) !== -1) return true;
        }
        return false;
      }

      function detectAuthType(url, data) {
        if (url.indexOf('/parent-login/') !== -1) return 'PARENT';
        if (url.indexOf('/qr-login/') !== -1) return 'PATIENT';
        if (data && data.role) {
          var r = data.role.toLowerCase();
          if (r === 'patient' || r === 'child') return 'PATIENT';
          if (r === 'parent') return 'PARENT';
        }
        if (data && data.account_type) {
          var a = data.account_type.toLowerCase();
          if (a === 'child') return 'PATIENT';
          if (a === 'parent') return 'PARENT';
        }
        return 'BEARER';
      }

      function notifyFlutter(token, authType) {
        try {
          window.flutter_inappwebview.callHandler('onAuthLogin', {
            token: token,
            type: authType
          });
        } catch(e) {
          console.log('FCM: flutter handler error', e);
        }
      }

      function logHeadersAndCookies(response) {
        console.log('FCM: Cookies after request:', document.cookie);
        if (response && response.headers) {
           var headersObj = {};
           response.headers.forEach(function(val, key) { headersObj[key] = val; });
           console.log('FCM: Response Headers:', JSON.stringify(headersObj));
        }
      }

      // === Перехват fetch ===
      var originalFetch = window.fetch;
      window.fetch = function(input, init) {
        var url = '';
        if (typeof input === 'string') {
          url = input;
        } else if (input && input.url) {
          url = input.url;
        }

        console.log('FCM: fetch called for URL:', url); // Логируем все fetch, чтобы найти второй шаг

        if (isLoginUrl(url)) {
          console.log('FCM: Intercepted login fetch to', url);
          return originalFetch.apply(this, arguments).then(function(response) {
            logHeadersAndCookies(response);
            var cloned = response.clone();
            cloned.json().then(function(data) {
              console.log('FCM: Login response keys:', Object.keys(data));
              console.log('FCM: Full response:', JSON.stringify(data).substring(0, 500));
              var accessToken = data.access || data.access_token || data.token;
              
              // Для ParentLoginResponse токены лежат внутри массива children
              if (!accessToken && data.children && data.children.length > 0) {
                 accessToken = data.children[0].access || data.children[0].token;
              }
              
              if (accessToken) {
                var authType = detectAuthType(url, data);
                if (data.children && data.children.length > 0) {
                    authType = 'PARENT'; // Принудительно ставим PARENT, если нашли токены в массиве
                }
                console.log('FCM: Got token, type=' + authType);
                notifyFlutter(accessToken, authType);
              } else {
                console.log('FCM: Access token NOT found in body. Are we using cookies?');
                // Если есть куки access_token/token
                var cookieMatch = document.cookie.match(/(?:^|;\\s*)(?:access|token|access_token)=([^;]*)/);
                if (cookieMatch) {
                    console.log('FCM: Found token in cookies!');
                    notifyFlutter(cookieMatch[1], detectAuthType(url, data));
                }
              }
            }).catch(function(e) {
              console.log('FCM: Could not parse login response', e);
            });
            return response;
          });
        }
        return originalFetch.apply(this, arguments);
      };

      // === Перехват XMLHttpRequest ===
      var originalXhrOpen = XMLHttpRequest.prototype.open;
      var originalXhrSend = XMLHttpRequest.prototype.send;

      XMLHttpRequest.prototype.open = function(method, url) {
        this.__fcmUrl = url;
        this.__fcmIsLogin = isLoginUrl(url || '');
        console.log('FCM: XHR open for URL:', url);
        return originalXhrOpen.apply(this, arguments);
      };

      XMLHttpRequest.prototype.send = function() {
        if (this.__fcmIsLogin) {
          var xhr = this;
          var url = xhr.__fcmUrl || '';
          console.log('FCM: Intercepted login XHR to', url);

          var originalOnReady = xhr.onreadystatechange;
          xhr.onreadystatechange = function() {
            if (xhr.readyState === 4 && xhr.status >= 200 && xhr.status < 300) {
              console.log('FCM: XHR Cookies after request:', document.cookie);
              console.log('FCM: XHR Headers:', xhr.getAllResponseHeaders());
              try {
                var data = JSON.parse(xhr.responseText);
                console.log('FCM: XHR Login response keys:', Object.keys(data));
                var accessToken = data.access || data.access_token || data.token;
                if (!accessToken && data.children && data.children.length > 0) {
                   accessToken = data.children[0].access || data.children[0].token;
                }
                
                if (accessToken) {
                  var authType = detectAuthType(url, data);
                  if (data.children && data.children.length > 0) {
                      authType = 'PARENT';
                  }
                  console.log('FCM: Got token from XHR, type=' + authType);
                  notifyFlutter(accessToken, authType);
                } else {
                  console.log('FCM: Access token NOT found in XHR body.');
                  var cookieMatch = document.cookie.match(/(?:^|;\\s*)(?:access|token|access_token)=([^;]*)/);
                  if (cookieMatch) {
                      notifyFlutter(cookieMatch[1], detectAuthType(url, data));
                  }
                }
              } catch(e) {
                console.log('FCM: Could not parse XHR login response', e);
              }
            }
            if (originalOnReady) originalOnReady.apply(this, arguments);
          };
        }
        return originalXhrSend.apply(this, arguments);
      };

      console.log('FCM: fetch/XHR interceptor installed');
    })();
  """;

  /// Внедрить перехватчик fetch/XHR в WebView для автоматического захвата логина
  static Future<void> injectFetchInterceptor(InAppWebViewController controller) async {
    try {
      await controller.evaluateJavascript(source: _fetchInterceptorJs);
      _fetchInterceptorInjected = true;
      debugPrint('FCM: Fetch interceptor injected');
    } catch (e) {
      debugPrint('FCM: Error injecting fetch interceptor: $e');
    }
  }

  /// Проверить авторизацию и отправить FCM токен
  static Future<void> checkAuthAndSendToken(InAppWebViewController? controller, BuildContext context) async {
    _webViewController = controller;

    // Если уже есть кэшированный токен — отправляем
    if (_authToken != null && _authType != null) {
      debugPrint('FCM: Using cached auth ($_authType), sending FCM token...');
      await _sendFcmTokenToServer(context);
      return;
    }

    debugPrint('FCM: No auth token yet, waiting for login via interceptor...');
  }

  /// Настройка Firebase Messaging
  static void setupFirebaseMessaging(
    void Function(Map<String, dynamic>, InAppWebViewController?) onTap,
    InAppWebViewController? controller,
    BuildContext context,
  ) {
    if (kIsWeb) return;

    _webViewController = controller;
    FirebaseMessaging.instance.requestPermission();

    if (defaultTargetPlatform == TargetPlatform.iOS) {
      FirebaseMessaging.instance.getAPNSToken().then((apns) {
        if (apns != null && !_isWaitingForApnsToken) {
          _isWaitingForApnsToken = true;
          Future.microtask(() {
            checkAuthAndSendToken(controller, context);
          });
        }
      }).catchError((_) {});
    }

    // При обновлении FCM токена — перерегистрируем на сервере
    FirebaseMessaging.instance.onTokenRefresh.listen((newToken) async {
      try {
        debugPrint('FCM: Token refreshed, re-registering...');
        _fcmTokenSent = false;
        await _sendFcmTokenToServer(context);
      } catch (_) {}
    });

    // Foreground notification
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      final notification = message.notification;
      final data = message.data;
      if (notification != null) {
        showLocalNotification(
          title: notification.title ?? '',
          body: notification.body ?? '',
          payload: jsonEncode(data),
        );
      }
    });

    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      onTap(message.data, controller);
    });

    FirebaseMessaging.onBackgroundMessage((RemoteMessage message) async {
      onTap(message.data, null);
    });

    Future.microtask(() {
      checkAuthAndSendToken(controller, context);
    });
  }

  /// Установить JS-хендлеры в WebView для перехвата логина/логаута
  static void setupWebViewAuthHandler(InAppWebViewController controller, BuildContext context) {
    _webViewController = controller;

    // Хендлер вызывается автоматически из fetch-интерцептора при успешном логине
    controller.addJavaScriptHandler(
      handlerName: 'onAuthLogin',
      callback: (args) async {
        debugPrint('FCM: onAuthLogin handler called with ${args.length} args');
        if (args.isNotEmpty) {
          final data = args[0];
          debugPrint('FCM: Auth data received: $data');
          if (data is Map && data['token'] != null) {
            _authToken = data['token'].toString();
            _authType = (data['type'] ?? 'BEARER').toString().toUpperCase();

            final prefs = await SharedPreferences.getInstance();
            await prefs.setString('auth_token', _authToken!);
            await prefs.setString('auth_type', _authType!);
            await prefs.setInt('auth_timestamp', DateTime.now().millisecondsSinceEpoch);

            debugPrint('FCM: Auth saved ($_authType), registering FCM token...');
            _fcmTokenSent = false;

            if (Platform.isIOS) {
              await _waitForApnsToken();
            }

            await _sendFcmTokenToServer(context);
          } else {
            debugPrint('FCM: onAuthLogin - invalid data format');
          }
        }
      },
    );

    // Хендлер для logout
    controller.addJavaScriptHandler(
      handlerName: 'onAuthLogout',
      callback: (args) async {
        debugPrint('FCM: onAuthLogout handler called');
        await deactivateFcmToken();
      },
    );
  }

  /// Показать локальное уведомление
  static Future<void> showLocalNotification({
    required String title,
    required String body,
    required String payload,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'magic_smile_channel',
      'MagicSmile Notifications',
      importance: Importance.max,
      priority: Priority.high,
    );
    const iosDetails = DarwinNotificationDetails();
    const notificationDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );
    await _localNotificationsPlugin.show(
      0,
      title,
      body,
      notificationDetails,
      payload: payload,
    );
  }

  /// Отправить FCM токен на сервер с JWT авторизацией
  static Future<void> _sendFcmTokenToServer(BuildContext context) async {
    if (kIsWeb) return;
    if (_fcmTokenSent) {
      debugPrint('FCM: Token already sent, skipping');
      return;
    }

    final uri = Uri.parse('$_apiBaseUrl/api/notifications/fcm-token/');

    if (Platform.isIOS) {
      try {
        final apnsToken = await FirebaseMessaging.instance.getAPNSToken();
        if (apnsToken == null) {
          final apnsReady = await _waitForApnsToken(maxAttempts: 5);
          if (!apnsReady) {
            debugPrint('FCM: APNS token not ready, aborting');
            return;
          }
        }
      } catch (_) {
        return;
      }
    }

    String? fcmToken = await FirebaseMessaging.instance.getToken();
    if (fcmToken == null) {
      debugPrint('FCM: getToken() returned null, regenerating...');
      await FirebaseMessaging.instance.deleteToken();
      if (Platform.isIOS) await _waitForApnsToken(maxAttempts: 5);
      fcmToken = await FirebaseMessaging.instance.getToken();
      if (fcmToken == null) {
        debugPrint('FCM: Still no FCM token, aborting');
        return;
      }
    }

    if (_authToken == null || _authType == null) {
      debugPrint('FCM: No auth token, cannot send FCM token');
      return;
    }

    debugPrint('FCM: Sending token to server...');
    debugPrint('FCM: Auth: $_authType ${_authToken!.substring(0, 20)}...');
    debugPrint('FCM: FCM token: ${fcmToken.substring(0, 20)}...');

    int retryCount = 0;
    const maxRetries = 3;

    while (retryCount < maxRetries) {
      try {
        final body = jsonEncode({
          'token': fcmToken,
          'device_id': await _getDeviceId(),
          'device_type': _getDeviceType(),
        });

        final response = await http.post(
          uri,
          headers: {
            'Content-Type': 'application/json',
            'Authorization': '$_authType $_authToken',
          },
          body: body,
        );

        debugPrint('FCM: Server response: ${response.statusCode}');
        debugPrint('FCM: Response body: ${response.body}');

        if (response.statusCode == 200 || response.statusCode == 201) {
          _fcmTokenSent = true;
          debugPrint('FCM: ✅ Token registered successfully!');
          return;
        } else if (response.statusCode == 401) {
          debugPrint('FCM: ❌ Auth token expired (401)');
          await _clearAuthCache();
          return;
        } else if (response.statusCode == 409) {
          debugPrint('FCM: Conflict (409), regenerating FCM token...');
          await FirebaseMessaging.instance.deleteToken();
          if (Platform.isIOS) await _waitForApnsToken(maxAttempts: 5);
          fcmToken = await FirebaseMessaging.instance.getToken();
          retryCount++;
          continue;
        } else {
          debugPrint('FCM: ❌ Unexpected status: ${response.statusCode}');
          return;
        }
      } catch (e) {
        debugPrint('FCM: ❌ Error sending: $e');
        return;
      }
    }
  }

  /// Деактивировать FCM токен на сервере при logout
  static Future<void> deactivateFcmToken() async {
    if (kIsWeb) return;

    try {
      final fcmToken = await FirebaseMessaging.instance.getToken();
      if (fcmToken == null || _authToken == null || _authType == null) {
        await _clearAuthCache();
        return;
      }

      final uri = Uri.parse('$_apiBaseUrl/api/notifications/fcm-token/');
      final response = await http.delete(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': '$_authType $_authToken',
        },
        body: jsonEncode({'token': fcmToken}),
      );

      debugPrint('FCM: Deactivate response: ${response.statusCode}');
    } catch (e) {
      debugPrint('FCM: Error deactivating: $e');
    } finally {
      await _clearAuthCache();
      _fcmTokenSent = false;
    }
  }

  /// Очистить кэш авторизации
  static Future<void> _clearAuthCache() async {
    _authToken = null;
    _authType = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('auth_type');
    await prefs.remove('auth_timestamp');
    debugPrint('FCM: Auth cache cleared');
  }
}
