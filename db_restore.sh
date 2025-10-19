#!/bin/bash
# db_restore.sh

set -e

# Базовые переменные
VPS_PATH="web-flbst-bot"

# Переменные для хранения введенных данных
VPS_IP=""
VPS_USER=""
BACKUP_FILE=""

# Функции
show_usage() {
    echo "Usage: $0 <backup_file_path>"
    echo "Restore script for Flibusta Bot databases"
    echo ""
    echo "Example: $0 /media/sf_FlibustaBot/backups/backup_20231201_120000.tar.gz"
}

prompt_user_input() {
    echo "🔐 VPS Connection Details"
    read -p "Enter VPS IP address [162.199.167.194]: " VPS_IP
    read -p "Enter VPS username [holy]: " VPS_USER

    VPS_IP=${VPS_IP:-"162.199.167.194"}
    VPS_USER=${VPS_USER:-"holy"}
}

validate_backup_file() {
    BACKUP_FILE="$1"

    if [ -z "$BACKUP_FILE" ]; then
        echo "❌ Error: Backup file path is required"
        show_usage
        exit 1
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        echo "❌ Error: Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    echo "📦 Using backup: $BACKUP_FILE"
}

stop_services() {
    echo "⏹️ Stopping services..."

    ssh $VPS_USER@$VPS_IP << EOF
    cd ~/$VPS_PATH
    docker-compose down || true
EOF
}

upload_backup() {
    echo "📤 Uploading backup to VPS..."

    scp "$BACKUP_FILE" $VPS_USER@$VPS_IP:~/$VPS_PATH/restore_backup.tar.gz
}

restore_databases() {
    echo "🔄 Restoring databases..."

    ssh $VPS_USER@$VPS_IP << EOF
    cd ~/$VPS_PATH

    tar -xzf restore_backup.tar.gz -C data/
    rm restore_backup.tar.gz
    chmod 664 data/*.sqlite 2>/dev/null || true

    echo "✅ Databases restored"
EOF
}

start_services() {
    echo "🚀 Starting services..."

    ssh $VPS_USER@$VPS_IP << EOF
    cd ~/$VPS_PATH
    docker-compose up -d
EOF
}

cleanup() {
    unset VPS_IP
    unset VPS_USER
    unset BACKUP_FILE
}

# Основной процесс
if [ $# -eq 0 ]; then
    echo "❌ Error: Backup file path is required"
    show_usage
    exit 1
fi

echo "🔄 Starting restore process..."
validate_backup_file "$1"
prompt_user_input
upload_backup
stop_services
restore_databases
start_services
cleanup
echo "🎉 Restore process completed successfully!"