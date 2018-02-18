# Simple Invoice

Simple in-house invoicing app

### Quickstart

Get the source from GitHub:

    git clone git@github.com:dobarkod/simple-invoice.git

Create Python2 virtual environment:

    mkvirtualenv --python=/usr/bin/python2 simple-invoice

Navigate to the project directory:

    cd simple-invoice

Install required files:

    pip install -r requirements.txt

Create '/simple-invoice/.env' file to define environment variables
showed in .env.sample, for example:

    DEBUG=true

Migrate the database:

    ./manage.py migrate

Create super user:

    ./manage.py createsuperuser

Run development server:

    ./manage.py runserver

Point your browser to http://127.0.0.1:8000/admin and login

Running tests:

    ./manage.py test
