@echo on

# mkdir cert
openssl req -x509 -nodes -newkey rsa:2048 -keyout ./cert/server.key -out ./cert/server.crt -days 365