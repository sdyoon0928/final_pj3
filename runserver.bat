@echo on

py manage.py runserver_plus 0.0.0.0:443 --key-file .\cert\server.key --cert-file .\cert\server.crt