# Flask imports
from flask import Flask
from flask import abort, redirect, session, flash, g
from flask import render_template, url_for
from flask import request
from flask import send_file
from werkzeug import secure_filename

# Python imports
from datetime import datetime
from functools import wraps
import os
import random
import sha
import shutil
import smtplib
import subprocess
import tarfile
import zipfile
try:
	import ldap
except:
	print "ldap not loaded"
from email.mime.text import MIMEText

# Pyboard imports
import serverconfig

app = Flask(__name__)
app.secret_key = serverconfig.app_secret_key

class User:
	def __init__(self, username):
		temp = open('users/' + username)
		self.username = username.strip()
		self.email = temp.readline().strip()
		self.section = temp.readline().strip()
		temp.close()

	def write(self):
		temp = open('users/' + self.username, 'w')
		temp.write(self.email + '\n')
		temp.write(self.section + '\n')
		temp.close()

def send_email(me = None, you = None, subject = 'Notification', body = None):
	if not me:
		me = serverconfig.email_from
	if not you or not body:
		return

	if type(you) is str or type(you) is unicode:
		you = [you]

	message = MIMEText(body)
	message['Subject'] = subject
	message['From'] = me
	message['To'] = ', '.join(you)

	s = smtplib.SMTP('localhost')
	s.sendmail(me, you, message.as_string())
	s.quit()

def requires_login(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if 'username' not in session:
			flash('You must be logged in to view this page.')
			return render_template('login.html')

		return func(*args, **kwargs)
	return wrapper

def requires_admin(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		if 'admin' != g.user.section:
			flash('You must be an administrator to view this page.')
			return redirect(url_for('index'))

		return func(*args, **kwargs)
	return wrapper

def validate_login(username, password):
	server = serverconfig.ldap_server
	con = ldap.initialize(server)
	dn = serverconfig.make_dn(username)
	rv = con.simple_bind(dn, password)

	try:
		r = con.result(rv)
		if r[0] == 97:
			return True
	except:
		pass

	return False

def handle_file(file_path):
	return_string = ""

	dir = os.path.dirname(file_path)
	ufile = os.path.basename(file_path)

	ext = ufile.split(".")[1:]
	ext = ".".join(ext)

	pdir = os.path.abspath(os.curdir)

	os.chdir(dir)

	if ext == "tar" or ext == "tar.gz":
		return_string += "tar or tar.gz file extension found\n"
		try:
			tf = tarfile.open(ufile)
			tf.extractall()
		except:
			return_string += "ERROR: could not open tar(.gz) file " + ufile + "\n"
			os.chdir(pdir)
			return return_string
		os.remove(ufile)
	elif ext == "zip":
		return_string += "zip file extension found\n"
		try:
			zf = zipfile.ZipFile(ufile)
			zf.extractall()
		except:
			return_string += "ERROR: could not open zip file " + ufile + "\n"
			os.chdir(pdir)
			return return_string
		os.remove(ufile)
	else:
		return_string += "Can't work with " + ufile + ". Don't know how.\n"
		os.chdir(pdir)
		return return_string

	return_string += "file successfully extracted\n"

	find = subprocess.Popen('find .', shell=True, stdout=subprocess.PIPE)
	return_string += "-\n" + find.communicate()[0].strip() + "\n-\n"

	os.mkdir('bin')
	return_string += "---running javac---\n"
	java = subprocess.Popen('javac -d bin -cp .:/usr/share/java/junit.jar **/*.java', shell=True, executable="/bin/zsh", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	jout = java.communicate()
	if jout[0] or jout[1]:
		return_string += "---javac error/warning output---\n"
	else:
		return_string += "---compilation successful---\n"
	if jout[0]:
		return_string += jout[0] + "\n"
	if jout[1]:
		return_string += jout[1] + "\n"


	os.chdir(pdir)

	return return_string

def get_submissions(section, assignment):
	pdir = os.path.abspath(os.curdir)
	dir = "files/" + "/" + section + "/" + assignment + "/"
	try:
		os.chdir(dir)
	except:
		os.chdir(pdir)
		return None
	os.chdir('..')
	file_name = section + "_" + assignment + ".tar.gz"
	tar = tarfile.open(file_name, "w:gz")
	tar.add(assignment)
	tar.close()

	os.chdir(pdir)

	shutil.move(dir + '../' + file_name, "static/" + file_name)
	return "static/" + file_name

def grades_for_user(username):
	grades = sorted([line.strip().split('\t') for line
		in open('grades/' + username) if line.strip()])
	grades = map(lambda x: (x[0], int(x[1]), int(x[2])), grades)
	total = reduce(lambda x, y: ('', x[1] + y[1], x[2] + y[2]), grades)
	return render_template('grades.html',
		grades=grades,
		total = total)

@app.before_request
def before():
	if 'username' in session:
		g.user = User(session['username'])

@app.route('/', methods=['GET', 'POST'])
@requires_login
def index():
	if request.method == 'POST':
		user = User(session['username'])

		ufile = request.files['file']
		filename = secure_filename(ufile.filename)
		assignment = request.form['ass']
		d = datetime.now()
		time_stamp = d.strftime("%Y-%m-%d-%H-%M-%S")
		upload_dir = "files/" + user.section + "/" + assignment + "/" + user.username + "/" + time_stamp + "/"

		try:
			os.makedirs(upload_dir)
		except:
			pass # uhh wat FIXME

		full_path = upload_dir + filename
		ufile.save(full_path)

		verification_code = sha.new(serverconfig.verification_salt + user.username + assignment).hexdigest()
		# FIXME template
		send_email(you = user.email,
			subject = 'Submission Received',
			body = "Your submission for assignment `" + assignment + "' was received.\n\nYour confirmation code is " + verification_code)

		output = handle_file(full_path)
		return render_template('upload.html', title='Upload',
			name = user.username,
			filename = filename,
			section = user.section,
			assignment = assignment,
			output = output)
	else:
		assignments = [line.strip() for line in open('assignments') if line.strip()]
		assignments.reverse()
		return render_template('index.html', title='Submit',
			assignments = assignments)

@app.route('/download/<section>/<assignment>', methods=['GET', 'POST'])
@requires_login
@requires_admin
def download(section, assignment):
	file_name = get_submissions(section, assignment)
	if file_name is None:
		return abort(404)
	return send_file(file_name, as_attachment=True)

@app.route('/admin')
@requires_login
@requires_admin
def admin():
	return render_template('admin.html')

@app.route('/profile', methods=['GET', 'POST'])
@app.route('/user/<username>')
@requires_login
def profile(username = None):
	if not username:
		username = session['username']
	try:
		user = User(username)
	except:
		return abort(404)

	if request.method == 'POST':
		user.email = request.form['new_email']
		user.write()

		flash('Email updated to "' + info[0] + '"')

	return render_template('profile.html',
		user = user,
		isuser = 'username' in session and session['username'] == username)

@app.route('/profile/edit')
@requires_login
def profile_edit():
	username = session['username']
	try:
		user = User(username)
	except:
		return abort(404)

	return render_template('profile_edit.html',
		user = user)

@app.route('/users')
@requires_login
def users():
	users = [User(user) for user in sorted(os.listdir('users'))]
	return render_template('users.html',
		title='Email List',
		users=users)

@app.route('/email/<to>', methods=['GET', 'POST'])
def email_to(to):
	if request.method == 'GET':
		return render_template('compose.html', to=to)
	else:
		yous = []

		users = [User(user) for user in sorted(os.listdir('users'))]
		for user in users:
			if to == 'a0' or to == user.section or user.section == 'admin':
				yous.append(user.email)

		send_email(me = request.form['from'],
			you = yous,
			subject = request.form['subject'],
			body = request.form['body'])

		return "message sent successfully"

@app.route('/grades')
@requires_login
def grades():
	return grades_for_user(session['username'])

@app.route('/admin/grades')
@app.route('/admin/grades/<username>')
@requires_login
@requires_admin
def grades_admin(username = None):
	if username is None:
		users = [User(user) for user in sorted(os.listdir('users'))]
		users = [user for user in users if user.section != 'admin']
		return render_template('class_grades.html',
			title = 'Class Grades',
			users = users)
	else:
		return grades_for_user(username)

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return render_template('login.html')
	else:
		if validate_login(request.form['username'], request.form['password']):
			session['username'] = request.form['username']
			flash('Logged in')
			return redirect(url_for('index'))

		flash('Invalid login')
		return redirect(url_for('login'))

@app.route('/logout')
def logout():
	session.pop('username', None)
	flash('Logged out')
	return redirect(url_for('login'))

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(500)
def view_error(error):
	try:
		return render_template('error.html',
			error = '{} Error'.format(error.code),
			desc = error.description), error.code

	except:
		return render_template('error.html',
			error = 'Oh my',
			desc = 'Something went wrong.')

if __name__ == '__main__':
	app.run(host='0.0.0.0', debug=True)
