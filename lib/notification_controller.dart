import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:flutter_inappwebview_platform_interface/flutter_inappwebview_platform_interface.dart';

class NotificationController {
  static final FlutterLocalNotificationsPlugin _localNotificationsPlugin =
      FlutterLocalNotificationsPlugin();

  static Future<void> initialize() async {
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings();
    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );
    await _localNotificationsPlugin.initialize(settings);
  }

  static Future<void> showLocalNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
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

    await _localNotificationsPlugin.show(0, title, body, notificationDetails, payload: payload);
  }

  static void setupFirebaseMessaging(
    void Function(Map<String, dynamic>) onTap,
    InAppWebViewController? controller,
  ) {
    FirebaseMessaging.instance.requestPermission();
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
      onTap(message.data);
    });
  }

  static Future<void> sendFcmTokenToServerIfAuthorized() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token == null) {
      print('⛔ Токен не получен');
      return;
    }

    final baseUrl = 'https://rabotniki.online';
    final uri = Uri.parse('$baseUrl/api/save-fcm-token');

    final cookieManager = CookieManager.instance();

    // 👇 Получаем CSRF cookie
    try {
      await http.get(Uri.parse('$baseUrl/sanctum/csrf-cookie'));
      print('✅ CSRF cookie запрошен');
    } catch (e) {
      print('❌ Ошибка при запросе CSRF cookie: $e');
      return;
    }

    // 👇 Получаем куки из WebView
    final cookies = await cookieManager.getCookies(url: WebUri(baseUrl));

    final hasSession = cookies.any((c) => c.name == 'laravel_session');
    if (!hasSession) {
      print('⛔ Пропускаем отправку токена — пользователь не авторизован (нет laravel_session)');
      return;
    }

final xsrf = cookies.firstWhere(
  (c) => c.name == 'XSRF-TOKEN',
  orElse: () => Cookie(name: '', value: ''),
);

if (xsrf.name.isEmpty || xsrf.value.isEmpty) {
  print('⛔ Нет XSRF-TOKEN в куках');
  return;
}



    final cookieHeader = cookies.map((c) => '${c.name}=${c.value}').join('; ');

    try {
      final response = await http.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Cookie': cookieHeader,
          if (xsrf != null) 'X-XSRF-TOKEN': Uri.decodeComponent(xsrf.value),
        },
        body: jsonEncode({'token': token}),
      );
      print('✅ FCM токен отправлен: ${response.statusCode}');
    } catch (e) {
      print('❌ Ошибка при отправке FCM токена: $e');
    }
  }
}
