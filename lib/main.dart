import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'notification_controller.dart';
import 'dart:io';
import 'package:flutter/foundation.dart';

Future<FirebaseApp> initializeDefaultApp() async {
  if (Firebase.apps.isNotEmpty) {
    return Firebase.app();
  }
  return await Firebase.initializeApp();
}

Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _initializeApp();
  runApp(MyApp());
}

Future<void> _initializeApp() async {
  try {
    await initializeDefaultApp();

    await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
  } on FirebaseException {
    // silent
  } catch (_) {
    // silent
  }

  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
  await NotificationController.initialize();
}


class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: const WebViewContainer(),
    );
  }
}

class WebViewContainer extends StatefulWidget {
  const WebViewContainer({super.key});

  @override
  _WebViewContainerState createState() => _WebViewContainerState();
}

class _WebViewContainerState extends State<WebViewContainer> {
  InAppWebViewController? _controller;
  bool _isLoading = true;
  late Future<SharedPreferences> _prefs;

  @override
  void initState() {
    super.initState();
    _prefs = SharedPreferences.getInstance();
    _requestPermissions();
  }

  Future<bool> _requestPermissions() async {
    final prefs = await _prefs;
    bool notificationRequested = prefs.getBool('notification_permission_requested') ?? false;

    // Камеру запрашиваем ВСЕГДА при старте — нужна для QR-сканера в WebView
    final cameraStatus = await Permission.camera.status;
    if (!cameraStatus.isGranted) {
      await Permission.camera.request();
    }

    // Фото
    final photosStatus = await Permission.photos.status;
    if (!photosStatus.isGranted && !photosStatus.isPermanentlyDenied) {
      await Permission.photos.request();
    }

    // Уведомления
    if (!notificationRequested && !kIsWeb) {
      final notificationStatus = await Permission.notification.status;
      if (!notificationStatus.isGranted && !notificationStatus.isPermanentlyDenied) {
        final result = await Permission.notification.request();
        await prefs.setBool('notification_permission_requested', true);
        if (!result.isGranted) {
          if (result.isPermanentlyDenied) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: const Text('Пожалуйста, включите уведомления в настройках устройства.'),
                duration: const Duration(seconds: 5),
                action: SnackBarAction(
                  label: 'Настройки',
                  onPressed: () => openAppSettings(),
                ),
              ),
            );
          }
          return false;
        }
      }
    } else {
      final notificationStatus = await Permission.notification.status;
      if (notificationStatus.isPermanentlyDenied) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Пожалуйста, включите уведомления в настройках устройства.'),
            duration: const Duration(seconds: 5),
            action: SnackBarAction(
              label: 'Настройки',
              onPressed: () => openAppSettings(),
            ),
          ),
        );
      }
    }

    return true;
  }

  void _handleNotificationClick(Map<String, dynamic> data, InAppWebViewController? controller) {
    final targetController = controller ?? _controller;
    String url = data['url'] ?? 'https://magicsmile.kz';
    // data.url может быть относительным путём — превращаем в полный URL
    if (!url.startsWith('http')) {
      url = 'https://magicsmile.kz$url';
    }
    if (targetController != null) {
      targetController.loadUrl(urlRequest: URLRequest(url: WebUri(url)));
    }
  }

  bool _isInternalUrl(String url) {
    return url.startsWith('https://magicsmile.kz') ||
        url.startsWith('http://magicsmile.kz');
  }

  Future<bool> _launchExternalUrl(String url, {String? scheme}) async {
    final Uri uri = Uri.parse(url);
    try {
      if (uri.scheme.isEmpty || uri.toString().isEmpty) {
        return false;
      }
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        return true;
      } else {
        return false;
      }
    } catch (e) {
      return false;
    }
  }

  void _showErrorSnackBar(String scheme, BuildContext context) {
    final schemeName = scheme == 'mailto'
        ? 'почтовое приложение'
        : scheme == 'tel'
            ? 'телефон'
            : scheme == 'sms'
                ? 'сообщения'
                : scheme == 'market'
                    ? 'Play Market'
                    : 'браузер';
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Не удалось открыть $schemeName. Убедитесь, что приложение для $schemeName установлено и настроено.'),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Stack(
          children: [
            InAppWebView(
              initialUrlRequest: URLRequest(url: WebUri('https://magicsmile.kz')),
              initialSettings: InAppWebViewSettings(
                javaScriptEnabled: true,
                useShouldOverrideUrlLoading: true,
                useOnDownloadStart: true,
                supportZoom: true,
                allowFileAccessFromFileURLs: true,
                allowUniversalAccessFromFileURLs: true,
                allowFileAccess: true,
                allowContentAccess: true,
                mediaPlaybackRequiresUserGesture: false,
                useHybridComposition: false,
                cacheMode: CacheMode.LOAD_DEFAULT,
                isTextInteractionEnabled: true,
                transparentBackground: Platform.isIOS,
                // Камера и медиа
                allowsInlineMediaPlayback: true,
                iframeAllow: "camera; microphone",
              ),
              onReceivedServerTrustAuthRequest: (controller, challenge) async {
                return ServerTrustAuthResponse(
                  action: ServerTrustAuthResponseAction.PROCEED,
                );
              },
              onWebViewCreated: (controller) {
                _controller = controller;
                NotificationController.setupFirebaseMessaging(_handleNotificationClick, controller, context);
                // JS-хендлеры для перехвата логина/логаута из фронтенда
                NotificationController.setupWebViewAuthHandler(controller, context);
                controller.evaluateJavascript(
                  source: """
                    document.addEventListener('focus', function(event) {
                      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
                        window.flutter_inappwebview.callHandler('onFocus');
                      }
                    }, true);
                  """,
                );
              },
              onLoadStart: (controller, url) {
                setState(() {
                  _isLoading = true;
                });
              },
              onLoadStop: (controller, url) async {
                setState(() {
                  _isLoading = false;
                });

                final currentUrl = url.toString();
                if (currentUrl.startsWith('https://magicsmile.kz')) {
                  // Внедряем перехватчик fetch/XHR на каждой странице
                  // чтобы поймать момент логина через API
                  await NotificationController.injectFetchInterceptor(controller);

                  // Если уже есть кэшированный auth — отправляем FCM токен
                  await Future.delayed(const Duration(milliseconds: 500));
                  Future.microtask(() {
                    NotificationController.checkAuthAndSendToken(controller, context);
                  });
                }
              },
              shouldOverrideUrlLoading: (controller, navigationAction) async {
                final url = navigationAction.request.url.toString();
                final scheme = url.split(':').first.toLowerCase();
                if (['mailto', 'tel', 'sms', 'market'].contains(scheme)) {
                  if (Platform.isIOS && scheme == 'market') {
                    final appStoreUrl = url.replaceFirst('market://', 'itms-apps://');
                    if (await _launchExternalUrl(appStoreUrl, scheme: 'itms-apps')) {
                      return NavigationActionPolicy.CANCEL;
                    } else {
                      _showErrorSnackBar('App Store', context);
                      return NavigationActionPolicy.CANCEL;
                    }
                  }
                  if (await _launchExternalUrl(url, scheme: scheme)) {
                    return NavigationActionPolicy.CANCEL;
                  } else {
                    _showErrorSnackBar(scheme, context);
                    return NavigationActionPolicy.CANCEL;
                  }
                } else if (!_isInternalUrl(url) && (url.startsWith('http:') || url.startsWith('https:'))) {
                  final bool? openInBrowser = await showDialog<bool>(
                    context: context,
                    builder: (context) => AlertDialog(
                      title: const Text('Открыть ссылку'),
                      content: const Text('Открыть во внешнем браузере или в приложении?'),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context, false),
                          child: const Text('В приложении'),
                        ),
                        TextButton(
                          onPressed: () => Navigator.pop(context, true),
                          child: const Text('В браузере'),
                        ),
                      ],
                    ),
                  );
                  if (openInBrowser == true) {
                    if (await _launchExternalUrl(url, scheme: scheme)) {
                      return NavigationActionPolicy.CANCEL;
                    } else {
                      _showErrorSnackBar('браузер', context);
                      return NavigationActionPolicy.CANCEL;
                    }
                  } else if (openInBrowser == false) {
                    return NavigationActionPolicy.ALLOW;
                  } else {
                    return NavigationActionPolicy.CANCEL;
                  }
                }
                return NavigationActionPolicy.ALLOW;
              },
              androidOnPermissionRequest: (controller, origin, resources) async {
                // Для камеры — проверяем разрешение и грантим WebView
                if (resources.contains('android.webkit.resource.VIDEO_CAPTURE') ||
                    resources.contains('android.webkit.resource.CAMERA') ||
                    resources.contains('android.webkit.resource.AUDIO_CAPTURE')) {
                  final cameraStatus = await Permission.camera.status;
                  if (cameraStatus.isGranted) {
                    return PermissionRequestResponse(
                      resources: resources,
                      action: PermissionRequestResponseAction.GRANT,
                    );
                  }
                  // Если не выдано — запрашиваем и грантим
                  final result = await Permission.camera.request();
                  return PermissionRequestResponse(
                    resources: resources,
                    action: result.isGranted
                        ? PermissionRequestResponseAction.GRANT
                        : PermissionRequestResponseAction.DENY,
                  );
                }
                // Для хранилища
                if (resources.contains('android.webkit.resource.PROTECTED_MEDIA_ID') ||
                    resources.contains('android.webkit.resource.STORAGE')) {
                  return PermissionRequestResponse(
                    resources: resources,
                    action: PermissionRequestResponseAction.GRANT,
                  );
                }
                return PermissionRequestResponse(
                  resources: resources,
                  action: PermissionRequestResponseAction.GRANT,
                );
              },
              onLoadError: (controller, url, code, message) async {
                setState(() {
                  _isLoading = false;
                });
                if (message.contains('ERR_UNKNOWN_URL_SCHEME')) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Не удалось загрузить ссылку. Попробуйте открыть в браузере.'),
                      duration: Duration(seconds: 3),
                    ),
                  );
                  await _launchExternalUrl(url.toString(), scheme: url?.scheme);
                  return;
                }
              },
            ),
            if (_isLoading)
              const Center(
                child: CircularProgressIndicator(),
              ),
          ],
        ),
      ),
    );
  }
}
