[app]

# 应用信息
title = 线号识别系统
package.name = wirerecognition
package.domain = com.wirerecognition
version = 1.0.0

# 源码
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,ini
source.exclude_exts = spec,ico,ui,bat,psd

# 版本号
version.code = 1
version.regex =
version.filename =

# 构建配置
requirements = python3,kivy==2.3.1,pandas,openpyxl,python-calamine,plyer

# Android 权限
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.sdk = 34
android.ndk = 25c
android.accept_sdk_license = True

# 架构
android.archs = arm64-v8a, armeabi-v7a

# 图标
android.icon = logo-512.png

# 启动画面
android.presplash_color = #1e40af
android.presplash_fill_width = True

# 签名
android.manifest_intent_filters =

# 调试
android.debug = False
android.release = True
android.enable_androidx = True

# 日志
android.logcat_filters = *:S python:V

# 窗口大小（桌面测试用）
window.width = 400
window.height = 700

# 服务
services =

# 构建输出
dist_dir = ./dist/android/

[buildozer]

# 日志级别
log_level = 2

# 警告
warn_on_root = 1

# Python 架构
python3.version = 3.11

# 构建时使用的 Docker 镜像（推荐）
docker_image = kivy/buildozer:1.5
