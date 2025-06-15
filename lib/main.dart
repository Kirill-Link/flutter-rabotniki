import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'notification_controller.dart';

Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  print("Handling a background message: ${message.messageId}");
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
  await NotificationController.initialize();

  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.white,
      statusBarIconBrightness: Brightness.dark,
      statusBarBrightness: Brightness.light,
    ),
  );

  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);

  runApp(const MyApp());
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
  final flutterLocalNotificationsPlugin = FlutterLocalNotificationsPlugin();

  @override
  void initState() {
    super.initState();
    _requestPermissions();
    NotificationController.setupFirebaseMessaging(_handleNotificationClick, _controller);
  }

  Future<bool> _requestPermissions() async {
    final statuses = await [
      Permission.camera,
      Permission.photos,
      Permission.notification,
    ].request();
    if (statuses[Permission.camera]!.isDenied || statuses[Permission.photos]!.isDenied) {
      _showNotification('Ошибка', 'Требуются разрешения на камеру и галерею');
      return false;
    }
    if (statuses[Permission.camera]!.isPermanentlyDenied || statuses[Permission.photos]!.isPermanentlyDenied) {
      _showNotification('Ошибка', 'Разрешения отклонены навсегда. Откройте настройки приложения');
      await openAppSettings();
      return false;
    }
    return true;
  }

  Future<void> _showNotification(String title, String body) async {
    const androidDetails = AndroidNotificationDetails(
      'rabotniki_channel',
      'Rabotniki Notifications',
      channelDescription: 'Notifications for Rabotniki app',
      importance: Importance.high,
      priority: Priority.high,
    );
    const iosDetails = DarwinNotificationDetails();
    const notificationDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );
    await flutterLocalNotificationsPlugin.show(0, title, body, notificationDetails);
  }

  void _handleNotificationClick(Map<String, dynamic> data) {
    final chatId = data['chatId'] as String?;
    if (chatId != null && chatId.isNotEmpty) {
      _controller?.loadUrl(
        urlRequest: URLRequest(
          url: WebUri('https://rabotniki.dat-studio.com/chat?chatId=$chatId'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final keyboardHeight = MediaQuery.of(context).viewInsets.bottom;

    return WillPopScope(
      onWillPop: () async {
        if (await _controller?.canGoBack() ?? false) {
          _controller?.goBack();
          return false;
        }
        return true;
      },
      child: SafeArea(
        child: Padding(
          padding: EdgeInsets.only(bottom: keyboardHeight),
          child: InAppWebView(
            initialUrlRequest: URLRequest(url: WebUri('https://rabotniki.dat-studio.com')),
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
              useHybridComposition: true,
            ),
            onWebViewCreated: (controller) {
              _controller = controller;
              NotificationController.setupFirebaseMessaging(_handleNotificationClick, controller);
            },
            onLoadStart: (controller, url) {
              print('Page started: $url');
            },
            onLoadStop: (controller, url) async {
              print('Page loaded: $url');

              // 🔐 Отправка FCM токена только после авторизации
              if (url.toString().contains("/account/setting") ||
                  url.toString().contains("/account") ||
                  url.toString().contains("/profile")) {
                await NotificationController.sendFcmTokenToServerIfAuthorized();
              }
            },
            shouldOverrideUrlLoading: (controller, navigationAction) async {
              print('Navigating to: ${navigationAction.request.url}');
              return NavigationActionPolicy.ALLOW;
            },
            androidOnPermissionRequest: (controller, origin, resources) async {
              if (resources.contains('android.webkit.resource.CAMERA') ||
                  resources.contains('android.webkit.resource.STORAGE')) {
                if (await _requestPermissions()) {
                  return PermissionRequestResponse(
                    resources: resources,
                    action: PermissionRequestResponseAction.GRANT,
                  );
                }
              }
              return PermissionRequestResponse(
                resources: resources,
                action: PermissionRequestResponseAction.DENY,
              );
            },
            onDownloadStartRequest: (controller, downloadStartRequest) async {
              print('Download started: ${downloadStartRequest.url}');
            },
          ),
        ),
      ),
    );
  }
}
