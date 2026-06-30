#!/bin/bash
set -e

echo "🚀 Starting AWSForge MCP setup..."

# 1. Create 4GB Swap for AI Memory
echo "🧠 Allocating 4GB Swap Space..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    echo "✅ Swapfile already exists. Skipping allocation."
fi

# 1.1 Update and install system dependencies (Forcing Python 3.12)
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y software-properties-common
# --- ADD THIS LINE TO FIX THE PYTHON 404 ---
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt-get update
# --------------------------------------------
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip git curl unzip nginx tmux jq

# 2. Install Terraform
echo "📦 Installing Terraform..."
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install -y terraform
terraform version

# 3. Install Ollama (background)
echo "🦙 Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl start ollama
# Pull model in background so we don't block setup
nohup ollama run phi3 > /dev/null 2>&1 &
echo "Ollama is pulling phi3 in the background."

# 4. Create project structure and move files
PROJECT_DIR="/opt/awsforge"
sudo mkdir -p $PROJECT_DIR
# Safely copy ALL files (including hidden ones) from current folder to /opt/awsforge
echo "📂 Copying repository files to $PROJECT_DIR..."
sudo cp -a "$PWD/." "$PROJECT_DIR/"
sudo chown -R $USER:$USER $PROJECT_DIR
cd $PROJECT_DIR
# Create necessary subdirectories
mkdir -p workspaces logs terraform_templates ui mcp_server/tools bootstrap
chmod 700 workspaces

#To check env file exists or not
if [ ! -f ".env" ]; then
    echo "⚠️ .env not found. Copying .env.example..."
    cp .env.example .env
fi

# 5. Python Virtual Environment
echo "🐍 Setting up Python environment..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt not found. Skipping pip install."
fi

# 6. AWS Configuration (Instance Role target)
mkdir -p ~/.aws
cat <<EOF > ~/.aws/config
[default]
region = ap-south-1
output = json
EOF

# 7. Setup Nginx Reverse Proxy
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/awsforge > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }

    # Explicitly protect the heavy AI endpoint
    location /chat {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Disable buffering so streaming isn't cached
        proxy_buffering off;
        
        # Extend connection limits to 15 minutes
        proxy_read_timeout 900;
        proxy_connect_timeout 900;
        proxy_send_timeout 900;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/awsforge /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

# 8. Setup Systemd Service
echo "⚙️ Configuring Systemd..."
sudo bash -c "cat > /etc/systemd/system/awsforge.service <<EOF
[Unit]
Description=AWSForge MCP Server
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PYTHONPATH=$PROJECT_DIR/mcp_server"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/uvicorn mcp_server.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF"
sudo systemctl daemon-reload
sudo systemctl enable awsforge.service
sudo systemctl start awsforge.service

# 9. Apply Bootstrap (AWS Budgets)
echo "💰 Setting up AWS Budgets Bootstrap..."

source .env
if [ -z "$ALERT_EMAIL" ]; then
    read -p "Enter email address for AWS Budget alerts: " ALERT_EMAIL
    echo "ALERT_EMAIL=$ALERT_EMAIL" >> .env
fi

cd bootstrap
terraform init -input=false
terraform apply -auto-approve -var="alert_email=${ALERT_EMAIL}"
cd ..

# 10. Make Kill Switch Executable
chmod +x nuke.sh

# Fix Database and Folder Permissions (CRITICAL)
echo "🔒 Setting final permissions..."
sudo chown -R $USER:$USER /opt/awsforge
sudo chmod -R 775 /opt/awsforge

IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")
echo "✅ Setup Complete!"
echo "🌐 UI accessible at: http://$IP/"
echo "☢️ REMINDER: run ./nuke.sh to destroy ALL resources when finished."
