# vMix Controller Mobile

Мобильная версия vMix контроллера для iOS и Android на Kivy

## Структура

```
mobile/
├── main.py          # Главное приложение
├── buildozer.spec   # Конфигурация для сборки
└── README.md        # Этот файл
```

## Сборка APK (Android)

```bash
cd mobile
buildozer android debug
```

Результат: `bin/vmixcontroller-0.1-debug.apk`

## Сборка для iOS

```bash
cd mobile
buildozer ios debug
```

Требует Xcode и iOS SDK
