FROM nginx:alpine
COPY index.html MiroScreenshot.png CursorCodeErstellung.png CursorCodeLauf.png /usr/share/nginx/html/
EXPOSE 80
