#!/bin/bash
# deploy.sh - Deployment script with functions and options

set -e

# Базовые переменные
DOCKER_USERNAME="holyshithappens"
DOCKER_IMAGE_NAME="web-flbst-bot"
IMAGE_NAME="$DOCKER_USERNAME/$DOCKER_IMAGE_NAME"
VPS_PATH="web-flbst-bot"
GITHUB_REPO="https://github.com/holyshithappens/flibusta_bot_web.git"
BRANCH="master"

# Переменные для хранения введенных данных
VPS_IP=""
VPS_USER=""
DOCKER_PASSWORD=""

# Функции
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo "Deploy script for Flibusta Bot"
    echo ""
    echo "Options:"
    echo "  -u, --update    Quick update (pull and restart containers)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Without options: Full deployment (build and deploy)"
}

prompt_user_input_vps() {
    echo "🔐 VPS Connection Details"
    read -p "Enter VPS IP address [162.199.167.194]: " input_ip
    read -p "Enter VPS username [holy]: " input_user

    VPS_IP=${input_ip:-"162.199.167.194"}
    VPS_USER=${input_user:-"holy"}
}

prompt_user_input_docker() {
    echo ""
    echo "🔐 Docker Hub authentication needed for user: $DOCKER_USERNAME"
    read -s -p "Enter Docker Hub password or access token: " DOCKER_PASSWORD
    echo
}

setup_directories_and_files() {
    echo ""
    echo "📁 Setting up directories and files on VPS..."

    ssh $VPS_USER@$VPS_IP << EOF
mkdir -p ~/$VPS_PATH/data ~/$VPS_PATH/logs ~/$VPS_PATH/tmp
EOF

    scp .env.vps $VPS_USER@$VPS_IP:$VPS_PATH/.env
    scp docker-compose.yml $VPS_USER@$VPS_IP:$VPS_PATH/docker-compose.yml
    #scp data/Flibusta_FB2_local.hlc2 $VPS_USER@$VPS_IP:$VPS_PATH/data/Flibusta_FB2_local.hlc2
    #scp data/FlibustaSettings.sqlite $VPS_USER@$VPS_IP:$VPS_PATH/data/FlibustaSettings.sqlite
    #scp data/FlibustaLogs.sqlite $VPS_USER@$VPS_IP:$VPS_PATH/data/FlibustaLogs.sqlite

    echo "✅ Directories and files setup completed"
}

setup_permissions() {
    echo ""
    echo "🔧 Setting permissions..."

    ssh $VPS_USER@$VPS_IP << EOF
cd ~/$VPS_PATH
sudo chown -R 1000:1000 data logs || true
sudo chmod -R 755 data logs || true
EOF

    echo "✅ Permissions setup completed"
}

build_and_push_image() {
    echo ""
    echo "🚀 Building and pushing Docker image..."

    ssh $VPS_USER@$VPS_IP << EOF
cd ~/$VPS_PATH

echo "📥 Cloning latest code from GitHub..."
rm -rf temp_build
git clone $GITHUB_REPO --branch $BRANCH --single-branch temp_build

echo "🔐 Logging into Docker Hub..."
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

echo "🐳 Building Docker image..."
docker build -t $IMAGE_NAME:latest ./temp_build

echo "📤 Pushing to Docker Hub..."
docker push $IMAGE_NAME:latest

echo "🔐 Logging out from Docker Hub..."
docker logout

echo "🧹 Cleaning up temp files..."
rm -rf temp_build

echo "✅ Image build and push completed"
EOF
}

deploy_containers() {
    echo ""
    echo "🚀 Deploying containers..."

    ssh $VPS_USER@$VPS_IP << EOF
cd ~/$VPS_PATH

echo "🔄 Starting containers..."
docker-compose down || true
docker-compose pull
docker-compose up -d --force-recreate

echo "🧹 Cleaning up Docker..."
docker system prune -f

echo "✅ Container deployment completed"
EOF
}

check_status() {
    echo ""
    echo "🔍 Checking service status..."

    ssh $VPS_USER@$VPS_IP << EOF
cd ~/$VPS_PATH
sleep 10
docker-compose ps
echo ""
docker-compose logs --tail=15
EOF

    echo "✅ Status check completed"
}

cleanup() {
    unset DOCKER_PASSWORD
    unset VPS_IP
    unset VPS_USER
}

# Обработка аргументов командной строки
case "${1:-}" in
    -u|--update)
        echo "🔄 Starting QUICK update..."
        prompt_user_input_vps
        deploy_containers
        check_status
        cleanup
        echo "✅ Quick update completed!"
        ;;

    -h|--help)
        show_usage
        ;;

    "")
        echo "🚀 Starting FULL deployment..."
        prompt_user_input_vps
        prompt_user_input_docker
        setup_directories_and_files
#        setup_permissions
        build_and_push_image
        deploy_containers
        check_status
        cleanup
        echo "✅ Full deployment completed!"
        ;;

    *)
        echo "Error: Unknown option $1"
        show_usage
        exit 1
        ;;
esac