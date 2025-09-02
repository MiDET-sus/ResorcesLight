# ResourceLight 🖥️

![Python](https://img.shields.io/badge/python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Version](https://img.shields.io/badge/version-1.0.0-orange.svg)

Легковесный и мощный системный монитор для Linux с интуитивным TUI-интерфейсом, написанный на Python.

![ResourceLight Screenshot](screenshot.png) <!-- Добавьте скриншот после -->

## ✨ Особенности

- 📊 Мониторинг в реальном времени: CPU, память, диски, сеть
- 🎨 Интуитивный TUI-интерфейс: Цветовая индикация состояния системы
- 📈 Исторические графики: Визуализация трендов нагрузки
- 🔔 Умные уведомления: Цветовые предупреждения при высокой нагрузке
- 📝 Топ процессов: Отображение самых ресурсоемких процессов
- ⚙️ Гибкая конфигурация: Настройка через JSON-файлы
- 📱 Адаптивный интерфейс: Автоподстройка под размер терминала
- 🔧 Горячие клавиши: Управление без мыши

## 🚀 Установка

### Способ 1: Прямая установка
`bash
# Клонируйте репозиторий
git clone https://github.com/ваш-username/resource-light.git
cd resource-light

# Установите зависимости
pip3 install -r requirements.txt

# Запустите
python3 src/resource_light.py
