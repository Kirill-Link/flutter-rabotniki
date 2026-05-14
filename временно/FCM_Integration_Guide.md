# FCM Push Notifications — Интеграция для мобильного приложения

## Базовый URL
```
https://api.magicsmile.kz
```

---

## Схемы авторизации

В проекте три типа пользователей, каждый со своим заголовком:

| Тип | Заголовок | Кто |
|-----|-----------|-----|
| Врач / менеджер | `Authorization: BEARER <token>` | JWT из `/api/login/` |
| Пациент (ребёнок) | `Authorization: PATIENT <token>` | JWT из `/api/game/auth/qr-login/` |
| Родитель | `Authorization: PARENT <token>` | JWT из `/api/game/auth/parent-login/` |

> ⚠️ Префикс обязательно заглавными буквами: `BEARER`, `PATIENT`, `PARENT`

---

## Флоу авторизации и регистрации FCM токена

### Вариант 1 — Пациент (вход по QR-коду)

```
1. GET  /api/game/auth/qr-info/{uuid}/   → получить инфо по QR
2. POST /api/game/auth/qr-login/         → получить access + refresh токены
3. POST /api/notifications/fcm-token/   → сохранить FCM токен
```

**Шаг 2 — QR логин:**
```http
POST /api/game/auth/qr-login/
Content-Type: application/json

{
  "token": "<временный токен из QR>"
}
```

Ответ:
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "role": "patient",
  "account_type": "child"
}
```

**Шаг 3 — Регистрация FCM токена:**
```http
POST /api/notifications/fcm-token/
Content-Type: application/json
Authorization: PATIENT eyJ...

{
  "token": "<FCM токен устройства от Firebase>",
  "device_id": "<уникальный ID устройства>",
  "device_type": "android"
}
```

Ответ:
```json
{
  "status": "ok",
  "message": "Токен сохранён."
}
```

---

### Вариант 2 — Родитель (вход по телефону и паролю)

```
1. POST /api/game/auth/parent-login/     → получить токены
2. POST /api/notifications/fcm-token/   → сохранить FCM токен
```

**Шаг 1 — Логин:**
```http
POST /api/game/auth/parent-login/
Content-Type: application/json

{
  "phone": "+7XXXXXXXXXX",
  "password": "пароль"
}
```

**Шаг 2 — Регистрация FCM токена:**
```http
POST /api/notifications/fcm-token/
Content-Type: application/json
Authorization: PARENT eyJ...

{
  "token": "<FCM токен устройства от Firebase>",
  "device_id": "<уникальный ID устройства>",
  "device_type": "android"
}
```

---

### Вариант 3 — Врач (JWT)

```
1. POST /api/login/                      → получить токены
2. POST /api/notifications/fcm-token/   → сохранить FCM токен
```

```http
POST /api/notifications/fcm-token/
Content-Type: application/json
Authorization: BEARER eyJ...

{
  "token": "<FCM токен>",
  "device_id": "<ID устройства>",
  "device_type": "android"
}
```

---

## Эндпоинт регистрации FCM токена

```
POST /api/notifications/fcm-token/
```

### Тело запроса

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `token` | string | ✅ | FCM токен от Firebase (`FirebaseMessaging.instance.getToken()`) |
| `device_id` | string | ❌ | Уникальный ID устройства |
| `device_type` | string | ❌ | `android` / `apple` / `web` / `unknown` |

### Ответы

| Код | Описание |
|-----|----------|
| 200 | Токен сохранён или обновлён |
| 400 | Невалидный токен (слишком короткий) |
| 401 | Не авторизован |

---

## Деактивация токена при выходе

При logout обязательно деактивировать токен:

```http
DELETE /api/notifications/fcm-token/
Content-Type: application/json
Authorization: BEARER eyJ...  (или PATIENT / PARENT)

{
  "token": "<FCM токен который нужно деактивировать>"
}
```

---

## Формат входящих уведомлений (FCM payload)

Уведомления приходят в стандартном FCM формате:

```json
{
  "notification": {
    "title": "Новый визит",
    "body": "Ваш визит назначен на 20 апреля"
  },
  "data": {
    "url": "/visits/42"
  }
}
```

Поле `data.url` — относительный путь для навигации внутри WebView после тапа на уведомление.

---

## Когда вызывать регистрацию FCM

```
Запуск приложения
    ↓
Проверить — есть ли сохранённый access токен?
    ├── НЕТ → показать экран входа (QR или телефон)
    │           ↓ после успешного логина
    │         получить FCM токен → POST /api/notifications/fcm-token/
    │
    └── ДА  → обновить FCM токен если изменился (onTokenRefresh)
                → POST /api/notifications/fcm-token/
```

**Важно:** FCM токен может обновиться — подписаться на `FirebaseMessaging.instance.onTokenRefresh` и повторно отправлять на сервер при каждом обновлении.

---

## Пример на Flutter (Dart)

```dart
Future<void> registerFcmToken(String authToken, String authType) async {
  // authType: 'BEARER', 'PATIENT', или 'PARENT'
  
  final fcmToken = await FirebaseMessaging.instance.getToken();
  if (fcmToken == null) return;

  final deviceId = await _getDeviceId();     // androidInfo.id / iosInfo.identifierForVendor
  final deviceType = Platform.isAndroid ? 'android' : 'apple';

  final response = await http.post(
    Uri.parse('https://api.magicsmile.kz/api/notifications/fcm-token/'),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': '$authType $authToken',
    },
    body: jsonEncode({
      'token': fcmToken,
      'device_id': deviceId,
      'device_type': deviceType,
    }),
  );
  
  // Подписаться на обновление токена
  FirebaseMessaging.instance.onTokenRefresh.listen((newToken) {
    registerFcmToken(authToken, authType);
  });
}
```

---

## google-services.json

Файл `google-services.json` для проекта `magicsmile-6a1bc` предоставлен отдельно.  
Положить в: `android/app/google-services.json`

---

## Контакты по вопросам

По вопросам интеграции обращаться к backend-разработчику проекта MagicSmile.
