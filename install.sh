#!/bin/bash
echo "Installing ResourceLight..."

# Создание директории для конфигурации
mkdir -p ~/.config/resourcelight

# Копирование скрипта
cp resource_light.py ~/.config/resourcelight/
chmod +x ~/.config/resourcelight/resource_light.py

# Создание конфигурационного файла
if [ ! -f ~/.config/resourcelight/config.json ]; then
  cat > ~/.config/resourcelight/config.json << EOF
{
  "refresh_interval": 1.0,
  "history_length": 60,
  "thresholds": {
    "cpu_warning": 70,
    "cpu_critical": 90,
    "mem_warning": 75,
    "mem_critical": 90,
    "disk_warning": 80,
    "disk_critical": 95
  },
  "disks_to_monitor": ["/"],
  "network_interfaces": ["eth0", "wlan0"],
  "log_file": "~/.config/resourcelight/resourcelight.log",
  "enable_logging": false
}
EOF
fi

# Создание символической ссылки для запуска из любого места
ln -sf ~/.config/resourcelight/resource_light.py /usr/local/bin/resourcelight

# Установка зависимостей
pip3 install psutil

echo "Installation complete. Run with: resourcelight"