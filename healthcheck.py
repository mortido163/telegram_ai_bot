#!/usr/bin/env python3
"""
Простой healthcheck для Docker контейнера
Проверяет базовое состояние бота без внешних зависимостей
"""

import os
import sys
from pathlib import Path


def check_process_by_pid():
    """Проверяет процесс по PID файлу"""
    try:
        pid_file = Path("/tmp/bot.pid")
        if not pid_file.exists():
            return False
            
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
            
        # Проверяем, что процесс существует
        try:
            os.kill(pid, 0)  # Сигнал 0 не убивает процесс, только проверяет существование
            return True
        except OSError:
            return False
            
    except Exception:
        return False


def check_environment():
    """Проверяет переменные окружения"""
    if not os.getenv('TELEGRAM_BOT_TOKEN'):
        print("ERROR: Environment variable TELEGRAM_BOT_TOKEN not set")
        return False
    
    return True


def check_basic_files():
    """Проверяет наличие основных файлов"""
    if not os.path.exists('/app/main.py'):
        print("ERROR: main.py not found")
        return False
    
    return True


def main():
    """Главная функция healthcheck"""
    try:
        # Базовые проверки
        if not check_environment():
            sys.exit(1)
            
        if not check_basic_files():
            sys.exit(1)
        
        # Проверяем PID файл
        if check_process_by_pid():
            print("OK: Process running")
            sys.exit(0)
        
        # Если PID файла нет, проверяем через pgrep
        try:
            import subprocess
            result = subprocess.run(
                ['pgrep', '-f', 'python.*main.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                print("OK: Process found via pgrep")
                sys.exit(0)
            else:
                print("ERROR: No bot process found")
                sys.exit(1)
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Если pgrep недоступен, считаем что все в порядке если базовые проверки прошли
            print("OK: Basic checks passed")
            sys.exit(0)
            
    except Exception as e:
        print(f"ERROR: Healthcheck failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
