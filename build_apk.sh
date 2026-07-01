#!/bin/bash
set -e
echo "=== 安装构建依赖 ==="
sudo apt-get update -qq
sudo apt-get install -y -qq gettext autopoint libtool automake
echo "=== 开始打包 APK ==="
yes | buildozer android debug
