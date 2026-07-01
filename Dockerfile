FROM kivy/buildozer:latest

USER root
RUN apt-get update -qq && \
    apt-get install -y -qq gettext autopoint && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER user
