#!/usr/bin/env python3
import psutil
import time
import curses
import argparse
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from collections import deque

# Конфигурация по умолчанию
DEFAULT_CONFIG = {
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
    "log_file": "~/.resource_light.log",
    "enable_logging": False
}

class ResourceLight:
    def __init__(self, config):
        self.config = config
        self.history = {
            "cpu": deque(maxlen=config["history_length"]),
            "mem": deque(maxlen=config["history_length"]),
            "disk": deque(maxlen=config["history_length"]),
            "net_up": deque(maxlen=config["history_length"]),
            "net_down": deque(maxlen=config["history_length"])
        }
        
        # Статистика сети
        self.last_net_io = psutil.net_io_counters()
        self.last_net_time = time.time()
        
        # Инициализация логирования
        if config["enable_logging"]:
            log_file = Path(config["log_file"]).expanduser()
            logging.basicConfig(
                filename=str(log_file),
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
        
        # Обработка сигналов для корректного завершения
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        curses.endwin()
        print("\nResourceLight завершает работу...")
        sys.exit(0)
    
    def get_cpu_usage(self):
        """Получение загрузки CPU"""
        return psutil.cpu_percent(interval=0.1)
    
    def get_memory_usage(self):
        """Получение использования памяти"""
        mem = psutil.virtual_memory()
        return mem.percent, mem.used // (1024 * 1024), mem.total // (1024 * 1024)
    
    def get_disk_usage(self):
        """Получение использования диска"""
        disk_usages = []
        for disk in self.config["disks_to_monitor"]:
            try:
                usage = psutil.disk_usage(disk)
                disk_usages.append((disk, usage.percent, usage.used // (1024 * 1024 * 1024), 
                                  usage.total // (1024 * 1024 * 1024)))
            except PermissionError:
                # Пропускаем диски, к которым нет доступа
                continue
        return disk_usages
    
    def get_network_usage(self):
        """Получение сетевой активности"""
        current_net_io = psutil.net_io_counters()
        current_time = time.time()
        
        time_diff = current_time - self.last_net_time
        up_speed = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / time_diff
        down_speed = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / time_diff
        
        # Сохраняем текущие значения для следующего расчета
        self.last_net_io = current_net_io
        self.last_net_time = current_time
        
        # Конвертируем в удобочитаемый формат
        return self.format_speed(up_speed), self.format_speed(down_speed)
    
    def get_network_interfaces(self):
        """Получение информации о сетевых интерфейсах"""
        interfaces = {}
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        
        for interface in self.config["network_interfaces"]:
            if interface in net_if_addrs:
                # Получаем IP-адрес
                ip_addr = "N/A"
                for addr in net_if_addrs[interface]:
                    if addr.family == 2:  # AF_INET
                        ip_addr = addr.address
                        break
                
                # Получаем статус
                status = "DOWN"
                if interface in net_if_stats and net_if_stats[interface].isup:
                    status = "UP"
                
                interfaces[interface] = {"ip": ip_addr, "status": status}
        
        return interfaces
    
    def get_top_processes(self, count=5):
        """Получение топ процессов по использованию CPU и памяти"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Сортируем по использованию CPU
        cpu_sorted = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:count]
        
        # Сортируем по использованию памяти
        mem_sorted = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)[:count]
        
        return cpu_sorted, mem_sorted
    
    def format_speed(self, bytes_per_sec):
        """Форматирование скорости сети"""
        if bytes_per_sec >= 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec:.1f} B/s"
    
    def format_bytes(self, bytes_val):
        """Форматирование размера в байтах"""
        if bytes_val >= 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"
        elif bytes_val >= 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        elif bytes_val >= 1024:
            return f"{bytes_val / 1024:.1f} KB"
        else:
            return f"{bytes_val} B"
    
    def get_color(self, value, warning, critical):
        """Получение цвета в зависимости от значения"""
        if value >= critical:
            return curses.COLOR_RED
        elif value >= warning:
            return curses.COLOR_YELLOW
        else:
            return curses.COLOR_GREEN
    
    def draw_bar(self, stdscr, y, x, label, value, max_value=100, width=20):
        """Отрисовка полоски индикатора"""
        # Рисуем label
        stdscr.addstr(y, x, f"{label}:")
        
        # Рассчитываем длину заполненной части
        filled = int(width * value / max_value)
        if filled > width:
            filled = width
        
        # Рисуем полоску
        bar = "[" + "#" * filled + " " * (width - filled) + "]"
        
        # Выбираем цвет
        color_pair = 1
        if "CPU" in label.upper():
            color_pair = self.get_color(value, self.config["thresholds"]["cpu_warning"], 
                                      self.config["thresholds"]["cpu_critical"]) + 1
        elif "MEM" in label.upper():
            color_pair = self.get_color(value, self.config["thresholds"]["mem_warning"], 
                                      self.config["thresholds"]["mem_critical"]) + 1
        elif "DISK" in label.upper():
            color_pair = self.get_color(value, self.config["thresholds"]["disk_warning"], 
                                      self.config["thresholds"]["disk_critical"]) + 1
        else:
            color_pair = curses.COLOR_GREEN + 1
        
        stdscr.addstr(y, x + len(label) + 2, bar, curses.color_pair(color_pair))
        
        # Добавляем значение
        if max_value == 100:  # Проценты
            stdscr.addstr(y, x + len(label) + 2 + width + 2, f"{value:.1f}%")
        else:  # Абсолютные значения
            stdscr.addstr(y, x + len(label) + 2 + width + 2, self.format_bytes(value))
    
    def update_history(self):
        """Обновление исторических данных"""
        cpu = self.get_cpu_usage()
        mem_percent, _, _ = self.get_memory_usage()
        
        # Для диска берем среднее по всем мониторируемым разделам
        disk_usages = self.get_disk_usage()
        disk_avg = sum(du[1] for du in disk_usages) / len(disk_usages) if disk_usages else 0
        
        net_up, net_down = self.get_network_usage()
        
        # Сохраняем в историю
        self.history["cpu"].append(cpu)
        self.history["mem"].append(mem_percent)
        self.history["disk"].append(disk_avg)
        self.history["net_up"].append(net_up)
        self.history["net_down"].append(net_down)
        
        # Логируем, если включено
        if self.config["enable_logging"]:
            logging.info(f"CPU: {cpu}%, MEM: {mem_percent}%, DISK: {disk_avg}%, "
                        f"NET_UP: {net_up}, NET_DOWN: {net_down}")
    
    def draw_history_graph(self, stdscr, y, x, data, label, height=5, width=30):
        """Отрисовка графика исторических данных"""
        if not data:
            return
        
        stdscr.addstr(y, x, f"{label} history:")
        
        # Находим максимальное значение для масштабирования
        max_val = max(data) if max(data) > 0 else 1
        
        # Рисуем график
        for i in range(height):
            line = ""
            for val in data:
                # Масштабируем значение к высоте графика
                scaled_val = (val / max_val) * height
                if scaled_val >= height - i:
                    line += "#"
                else:
                    line += " "
            
            stdscr.addstr(y + i + 1, x, line)
    
    def run(self, stdscr):
        """Основной цикл отрисовки"""
        # Инициализация цветов
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # Зеленый
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # Желтый
        curses.init_pair(3, curses.COLOR_RED, -1)     # Красный
        curses.init_pair(4, curses.COLOR_CYAN, -1)    # Голубой
        curses.init_pair(5, curses.COLOR_MAGENTA, -1) # Пурпурный
        
        # Включаем неблокирующий ввод
        stdscr.nodelay(True)
        stdscr.clear()
        
        # Основной цикл
        while True:
            # Получаем размер терминала
            height, width = stdscr.getmaxyx()
            
            # Обновляем данные
            self.update_history()
            
            # Очищаем экран
            stdscr.clear()
            
            # Заголовок
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            stdscr.addstr(0, 0, f"ResourceLight - System Monitor - {current_time}", 
                         curses.A_BOLD | curses.color_pair(4))
            
            # Разделительная линия
            stdscr.addstr(1, 0, "=" * width)
            
            # Основные метрики
            cpu_usage = self.get_cpu_usage()
            mem_percent, mem_used, mem_total = self.get_memory_usage()
            disk_usages = self.get_disk_usage()
            net_up, net_down = self.get_network_usage()
            net_interfaces = self.get_network_interfaces()
            
            # CPU
            self.draw_bar(stdscr, 3, 2, "CPU", cpu_usage)
            
            # Память
            self.draw_bar(stdscr, 4, 2, "Memory", mem_percent)
            stdscr.addstr(4, 50, f"({mem_used} MB / {mem_total} MB)")
            
            # Диски
            row = 5
            for disk, usage, used_gb, total_gb in disk_usages:
                self.draw_bar(stdscr, row, 2, f"Disk {disk}", usage)
                stdscr.addstr(row, 50, f"({used_gb} GB / {total_gb} GB)")
                row += 1
            
            # Сеть
            stdscr.addstr(row, 2, f"Network: ▲ {net_up} ▼ {net_down}", curses.color_pair(5))
            row += 1
            
            # Сетевые интерфейсы
            for i, (iface, info) in enumerate(net_interfaces.items()):
                status_color = curses.color_pair(1) if info["status"] == "UP" else curses.color_pair(3)
                stdscr.addstr(row + i, 2, f"{iface}: {info['ip']} [{info['status']}]", status_color)
            
            # Разделительная линия
            separator_row = row + len(net_interfaces) + 1
            if separator_row < height:
                stdscr.addstr(separator_row, 0, "=" * width)
            
            # Графики истории
            graph_row = separator_row + 1
            if graph_row + 8 < height:
                # CPU history
                self.draw_history_graph(stdscr, graph_row, 2, list(self.history["cpu"]), "CPU")
                
                # Memory history
                self.draw_history_graph(stdscr, graph_row, 40, list(self.history["mem"]), "Memory")
            
            # Топ процессов (если есть место)
            process_row = graph_row + 8
            if process_row + 10 < height:
                cpu_top, mem_top = self.get_top_processes(3)
                
                stdscr.addstr(process_row, 2, "Top CPU processes:", curses.A_BOLD)
                for i, proc in enumerate(cpu_top):
                    if process_row + i + 1 < height:
                        stdscr.addstr(process_row + i + 1, 2, 
                                     f"{proc['name']}: {proc['cpu_percent']:.1f}%")
                
                stdscr.addstr(process_row, 40, "Top MEM processes:", curses.A_BOLD)
                for i, proc in enumerate(mem_top):
                    if process_row + i + 1 < height:
                        stdscr.addstr(process_row + i + 1, 40, 
                                     f"{proc['name']}: {proc['memory_percent']:.1f}%")
            
            # Подсказки внизу экрана
            if height > 2:
                help_text = "Q: Quit | R: Refresh config | L: Toggle logging"
                stdscr.addstr(height - 1, 0, help_text, curses.A_DIM)
            
            # Обновляем экран
            stdscr.refresh()
            
            # Обработка ввода
            try:
                key = stdscr.getch()
                if key == ord('q') or key == ord('Q'):
                    break
                elif key == ord('r') or key == ord('R'):
                    # Перезагрузка конфигурации
                    self.load_config()
                elif key == ord('l') or key == ord('L'):
                    # Переключение логирования
                    self.config["enable_logging"] = not self.config["enable_logging"]
                    if self.config["enable_logging"]:
                        logging.info("Logging enabled")
                    else:
                        logging.info("Logging disabled")
            except curses.error:
                pass
            
            # Ждем перед следующим обновлением
            time.sleep(self.config["refresh_interval"])
    
    def load_config(self):
        """Загрузка конфигурации из файла"""
        config_path = Path("~/.resource_light.json").expanduser()
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    # Обновляем только существующие ключи
                    for key in user_config:
                        if key in self.config:
                            if isinstance(self.config[key], dict) and isinstance(user_config[key], dict):
                                self.config[key].update(user_config[key])
                            else:
                                self.config[key] = user_config[key]
                logging.info("Configuration reloaded")
            except Exception as e:
                logging.error(f"Error loading config: {e}")

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="ResourceLight - Lightweight system monitor")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--interval", type=float, help="Refresh interval in seconds")
    parser.add_argument("--log", action="store_true", help="Enable logging")
    parser.add_argument("--no-ui", action="store_true", help="Run in headless mode")
    
    args = parser.parse_args()
    
    # Загрузка конфигурации
    config = DEFAULT_CONFIG.copy()
    
    if args.config:
        try:
            with open(args.config, 'r') as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception as e:
            print(f"Error loading config: {e}")
            return
    
    if args.interval:
        config["refresh_interval"] = args.interval
    
    if args.log:
        config["enable_logging"] = True
    
    # Создание и запуск монитора
    monitor = ResourceLight(config)
    
    if args.no_ui:
        # Режим без UI (для скриптов)
        try:
            while True:
                monitor.update_history()
                print(f"CPU: {monitor.history['cpu'][-1]:.1f}%, "
                      f"MEM: {monitor.history['mem'][-1]:.1f}%, "
                      f"DISK: {monitor.history['disk'][-1]:.1f}%")
                time.sleep(config["refresh_interval"])
        except KeyboardInterrupt:
            print("\nStopping...")
    else:
        # Запуск в режиме с UI
        try:
            curses.wrapper(monitor.run)
        except KeyboardInterrupt:
            print("\nResourceLight stopped")

if __name__ == "__main__":
    main()