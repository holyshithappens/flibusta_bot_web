#!/bin/bash
# db_backup.sh

set -e

# Базовые переменные
VPS_PATH="web-flbst-bot"
BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Переменные для хранения введенных данных
VPS_IP=""
VPS_USER=""
LOCAL_BACKUP_DIR=""

# Функции
prompt_user_input() {
    echo "🔐 VPS Connection Details"
    read -p "Enter VPS IP address [162.199.167.194]: " VPS_IP
    read -p "Enter VPS username [holy]: " VPS_USER
    read -p "Enter local backup directory [/media/sf_FlibustaBot/backups]: " LOCAL_BACKUP_DIR

    VPS_IP=${VPS_IP:-"162.199.167.194"}
    VPS_USER=${VPS_USER:-"holy"}
    LOCAL_BACKUP_DIR=${LOCAL_BACKUP_DIR:-"/media/sf_FlibustaBot/backups"}
}

create_backup_vps() {
    echo "🔄 Creating backup on VPS..."

    ssh $VPS_USER@$VPS_IP << EOF
    mkdir -p ~/$VPS_PATH/$BACKUP_DIR

    cd ~/$VPS_PATH
    tar -czf $BACKUP_DIR/backup_$TIMESTAMP.tar.gz \
        data/FlibustaSettings.sqlite \
        data/FlibustaLogs.sqlite \
        2>/dev/null || echo "⚠️  Some databases might not exist yet"

    find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

    echo "✅ Backup created on VPS: backup_$TIMESTAMP.tar.gz"
    ls -lh $BACKUP_DIR/backup_$TIMESTAMP.tar.gz
EOF
}

download_backup() {
    echo "📥 Downloading backup to local machine..."

#    mkdir -p $LOCAL_BACKUP_DIR
    scp $VPS_USER@$VPS_IP:~/$VPS_PATH/$BACKUP_DIR/backup_$TIMESTAMP.tar.gz $LOCAL_BACKUP_DIR/

    if [ -f "$LOCAL_BACKUP_DIR/backup_$TIMESTAMP.tar.gz" ]; then
        echo "✅ Backup successfully downloaded to: $LOCAL_BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
        echo "📊 File size: $(du -h $LOCAL_BACKUP_DIR/backup_$TIMESTAMP.tar.gz | cut -f1)"
    else
        echo "❌ Failed to download backup"
        exit 1
    fi
}

cleanup() {
    unset VPS_IP
    unset VPS_USER
    unset LOCAL_BACKUP_DIR
}

# Основной процесс
echo "📦 Starting backup process..."
prompt_user_input
create_backup_vps
download_backup
cleanup
echo "🎉 Backup process completed successfully!"