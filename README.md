A Conference Registration App
=============================

This is a super basic registration web app I wrote for a the OWASP New Zealand Day conference because I had some spare time and nothing immediately jumped out that would do what we wanted.
It's written in python using the flask framework and was thrown together pretty quickly, so no guarantees on code quality or anything. The app saves all registrations in a sqlite3 database (main.db) which you'll need to query/export manually to pull the data out.

Contributions are welcome.


Install
-------

You probably want to use virtualenv and install these pip packages:

	Flask==0.10.1
	Flask-Mail==0.9.0
	Jinja2==2.7
	MarkupSafe==0.18
	Werkzeug==0.9.3
	argparse==1.2.1
	blinker==1.3
	distribute==0.6.34
	itsdangerous==0.22
	wsgiref==0.1.2

Then you can "python app.py debug" which runs the app in debug mode (not for production). At this point you'll want to 

* Set the app secret key, max registrations, and from email at the top of app.py
* Edit all templates and change as necessary (your logo, email address, etc)
* Configure some sort of local SMTP server, or configure Flask-Mail to use something else

I used gunicorn behind nginx in production to serve the app in production and you'll also need to setup a 10 minute cron job that runs "python app.py cleanup" to ensure unconfirmed registrations are expired etc. Audit logs are output to stderr which gunicorn can log for you somewhere.

That's it!


