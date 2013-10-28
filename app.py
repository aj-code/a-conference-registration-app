import binascii, re, os, sqlite3, datetime, config, sys
from flask import Flask, render_template, request, session, abort, redirect, url_for
from flask.ext.mail import Mail, Message

app = Flask(__name__)
mail = Mail(app)

#change this to your con/meetup size
maxRegistrations = 300 

#change this to something secret
app.secret_key = 'CHANGEME'

#emails come from this address
fromEmail = 'something@example.com'

#probably leave this as is
tokenCharLength = 40




## Controller Methods Begin ##

@app.route('/')
def index():
	
	if getRegistrationCount() >= maxRegistrations:
		regMaxedOut = True
	else:
		regMaxedOut = False
	
	
	return render_template('index.html', regMaxedOut = regMaxedOut)
	
@app.route('/register', methods=['POST'])
def register():
	
	if getRegistrationCount() >= maxRegistrations:
		return redirect(url_for('index'))
	
	
	firstName = sanitiseString(request.form['firstName'])
	lastName = sanitiseString(request.form['lastName'])
	affiliation = sanitiseString(request.form['affiliation'])
	region = sanitiseString(request.form['region'])
	email = sanitiseString(request.form['email'])
	additionalEmail = sanitiseString(request.form['additionalEmail'])
	
	if not firstName or not lastName or not email:
		abort(418, 'Required information missing such as firstName, lastName, and/or email. Turn on JavaScript like normal people.')
		
	managementToken = createRandToken()
	
	with getDB() as conn:
		sql = "INSERT INTO registrations (managementToken, firstName, lastName, affiliation, region, email, additionalEmail, cancelled, confirmed, createDate) VALUES (?,?,?,?,?,?,?,0,0,datetime(CURRENT_TIMESTAMP, 'localtime'))"	
		conn.execute(sql, (managementToken, firstName, lastName, affiliation, region, email, additionalEmail))
	
		message = render_template('registration_received_email.txt', token=managementToken)
		sendEmail(email, additionalEmail, "OWASP Day 2013 - Please Confirm Your Registration", message)
	
		auditLog('Got new registration with token: %s and email %s, %s' % (managementToken, email, additionalEmail), getIP())
	
	return render_template('register_begin.html')

@app.route('/manage/<token>/cancel', methods=['POST','GET'])
def cancel(token):
	
	if not validateToken(token):
		abort(404)
	
	if (request.method == 'GET'): #Confirm cancel
		
		with getDB() as conn:
			sql = 'SELECT firstName, lastName FROM registrations WHERE managementToken = ?'
			name = conn.execute(sql, (token,)).fetchone()
			
		return render_template('register_cancel.html', firstName=name[0], lastName=name[1])
	
	else: #Do cancel
		
		with getDB() as conn:		
			sql = 'UPDATE registrations SET cancelled = 1 WHERE managementToken = ?'
			conn.execute(sql, (token,))
			
			sql = 'SELECT firstName, lastName, email, additionalEmail FROM registrations WHERE managementToken = ?'
			details = conn.execute(sql, (token,)).fetchone()
			name = '%s %s' % (details[0], details[1])
			
			message = render_template('registration_cancelled_email.txt', name=name)
			sendEmail(details[2], details[3], "OWASP Day 2013 - Registration Cancelled", message)

			
		auditLog('Cancelled registration with token: %s' % token, getIP())
		
		return render_template('register_cancel.html')

@app.route('/manage/<token>/confirm')
def confirm(token):

	if not validateToken(token):
		abort(404)
	
	with getDB() as conn:		
		sql = 'UPDATE registrations SET confirmed = 1 WHERE managementToken = ?'
		conn.execute(sql, (token,))

		sql = 'SELECT firstName, lastName, affiliation, region, email, additionalEmail FROM registrations WHERE managementToken = ?'
		details = conn.execute(sql, (token,)).fetchone()		
		
		message = render_template('registration_confirmed_email.txt',
			token=token,
			firstName = details[0],
			lastName = details[1],
			affiliation = details[2],
			region = details[3])
		sendEmail(details[4], details[5], "OWASP Day 2013 - Registration Confirmed", message)
		
		auditLog('Confirmed registration with token: %s' % token, getIP())
	
	return render_template('register_confirmed.html')


## Helper Methods Begin ##

def getRegistrationCount():
	with getDB() as conn:
		sql = 'SELECT COUNT(*) FROM registrations WHERE cancelled = 0'
		return conn.execute(sql).fetchone()[0]
	

def validateToken(token):
	if re.match('^[0-9a-f]+$', token) is None:
		return False
				
	with getDB() as conn:
		sql = 'SELECT COUNT(*) FROM registrations WHERE managementToken = ? AND cancelled = 0'	
		rows = conn.execute(sql, (token,)).fetchone()[0]
		
		return rows == 1
	
def sanitiseString(str):
	""" Simple sanitisation, this is mostly because I'm not sure if the SMTP library is injectable. Also out of paranoia.  """
	
	if str is None: return None
	return str.replace('\x00', '').replace('\n','').replace('\r','').replace('>','').replace('<','')
	
def sendEmail(to, cc, subject, message):
	
	to = sanitiseString(to)
		
	msg = Message(subject=subject, sender = fromEmail, recipients = [to], body=message)
	
	if cc:
		cc = sanitiseString(cc)
		msg.cc = [cc]
		
	mail.send(msg)
			

def createRandToken():
	return binascii.hexlify(os.urandom(tokenCharLength/2))

def getIP():
	ip = request.headers.get('X-Forwarded-For')
	if ip is None:
		ip = request.remote_addr
	return ip

def getAppRoot():
	return os.path.dirname(os.path.realpath(__file__))
	
def auditLog(message, ip = None):
	now = datetime.datetime.now()

	if ip is None:
		sys.stderr.write('%s :: %s\n' % (now, message))
	else:
		sys.stderr.write('%s :: IP - %s :: %s\n' % (now, ip, message))
		
def getDB():
	needCreateTable = not os.path.exists('main.db')
	
	conn = sqlite3.connect('main.db')
	if needCreateTable:
		createTable(conn)
	
	return conn
	
def createTable(conn):

	sql = """CREATE TABLE registrations (
				id INTEGER PRIMARY KEY,
				firstName TEXT,
				lastName TEXT,
				affiliation TEXT,
				region TEXT,
				email TEXT,
				additionalEmail TEXT,
				managementToken TEXT,
				confirmed NUMERIC,
				cancelled NUMERIC,
				createDate TEXT
			);
		"""
	conn.execute(sql)
		
#CSRF shiz
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(418, "Double or Illegal Submission Detected. Please go to the homepage, refresh, and start again.")

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = createRandToken()
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token



#app cleanup - should be run by cron every 10mins or so
def doCleanup():
	with getDB() as conn:
		sql = "UPDATE registrations SET cancelled = 1 WHERE confirmed = 0 AND createDate < datetime(CURRENT_TIMESTAMP, 'localtime', '-12 Hour')"
		conn.execute(sql)


def printUsage():
	print 'Usage: python app.py debug|cleanup'	

if __name__ == "__main__":

	if len(sys.argv) != 2:
		printUsage()

	elif sys.argv[1] == 'debug':
		auditLog('OWASP Reg Instance Starting')
		app.run(debug = True, port=8000)
		
	elif sys.argv[1] == 'cleanup':
		doCleanup()
		
	else:
		printUsage()
