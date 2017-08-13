import os

import psycopg2
from flask import Flask, session, redirect, url_for, request, send_from_directory
from flask import render_template, flash
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
app = Flask(__name__)
UPLOAD_FOLDER = app.root_path + '/static/pix/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.urandom(16)
SESSION_TYPE = 'filesystem'
app.config.from_object(__name__)

conn = psycopg2.connect("host=localhost dbname=intranet password=master user=postgres")


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/')
def hello_world():
    session['usuario'] = None
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        user = str(request.form.get('user'))
        password = str(request.form.get('password'))
        ip = request.remote_addr
        hostname = request.host
        cur = conn.cursor()
        cur.execute("SELECT intranet.autentica(%s, %s, %s, %s);", (user, password, ip, hostname))
        result = cur.fetchone()
        cur.close()
        if result[0] is True:
            session['usuario'] = user
            return render_template('index.html')
        else:
            flash(u'Usuário ou senha inválida')
        return render_template('login.html')


@app.route('/foto_upload', methods=['GET', 'POST'])
def foto_upload():
    if request.method == 'POST':
        album_id = str(request.form.get('album_id'))
        file = request.files['upload']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur = conn.cursor()
            cur.execute("insert into intranet.foto (album_id, arquivo) values (%s, %s);", (album_id, filename))
            conn.commit()
            cur.close()
            return redirect(url_for('fotos', id=album_id))


@app.route('/albuns')
def albuns():
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM intranet.album;")
    albuns = cur.fetchall()
    cur.close()
    return render_template('albuns.html', albuns=albuns)


@app.route('/add_album', methods=['POST'])
def add_album():
    album = str(request.form.get('album'))
    cur = conn.cursor()
    cur.execute("insert into intranet.album(nome) values(%s);", (album,))
    conn.commit()
    cur.close()
    return redirect("/albuns")


@app.route('/fotos/<id>')
def fotos(id):
    cur = conn.cursor()
    cur.execute("SELECT arquivo, nome FROM intranet.foto, intranet.album where foto.album_id = album.id and album_id = %s;", (id,))
    fotos = cur.fetchall()
    cur.close()

    return render_template('fotos.html', fotos=fotos, album_id=id)


if __name__ == '__main__':
    app.run()
