from pyimagesearch.motion_detection import SingleMotionDetector
from imutils.video import VideoStream
from flask import Flask,render_template,flash,redirect,url_for,session,logging,request,Response
from flaskext.mysql import MySQL
from pymysql.cursors import DictCursor
from wtforms import Form,StringField,TextAreaField,PasswordField,validators
from passlib.hash import sha256_crypt
import threading
import argparse
import datetime
import imutils
import time
import cv2


class RegisterForm(Form):

    name = StringField("İsim Soyisim", validators=[validators.Length(
        min=4, max=25, message="4 ile 25 Arası Karakter Giriniz."), validators.DataRequired(message="Lütfen Bu Alanı Doldurunuz.")])
    email = StringField("Email Adresi", validators=[validators.DataRequired(
        message="Lütfen Bu Alanı Doldurunuz."), validators.Email(message="Geçerli Bir Email Adresi Giriniz...")])
    username = StringField("Kullanıcı Adı", validators=[validators.Length(
        min=5, max=35), validators.DataRequired(message="Lütfen Bu Alanı Doldurunuz.")])
    password = PasswordField("Parola", validators=[validators.DataRequired(), validators.EqualTo(
        fieldname="confirm", message="Parolalar Uyuşmuyor."), validators.DataRequired(message="Lütfen Bu Alanı Doldurunuz.")])
    confirm = PasswordField("Parola Tekrar")


class LoginForm(Form):
    username = StringField("Kullanıcı adı")
    password = PasswordField("PAROLA")


outputFrame = None
lock = threading.Lock()

# initialize a flask object

application = Flask(__name__)

application.secret_key = "xena"
application.config["MYSQL_DATABASE_HOST"] = "localhost"
application.config["MYSQL_DATABASE_USER"] = "root"
application.config["MYSQL_DATABASE_PASSWORD"] = ""
application.config["MYSQL_DATABASE_DB"] = "xena1"
application.config["MYSQL_CURSORCLASS"] = "DictCursor"

mysql = MySQL()
mysql.init_app(application)


# initialize the video stream and allow the camera sensor to
# warmup
#vs = VideoStream(usePiCamera=1).start()



@application.route('/')
def index():
    return render_template('index.html')


@application.route('/home')
def home():
    vs = VideoStream(src=0).start()
    time.sleep(2.0)
    return render_template('home.html')


def detect_motion(frameCount):
    # grab global references to the video stream, output frame, and
    # lock variables
    global vs, outputFrame, lock

    # initialize the motion detector and the total number of frames
    # read thus far
    md = SingleMotionDetector(accumWeight=0.1)
    total = 0

    # loop over frames from the video stream
    while True:
        # read the next frame from the video stream, resize it,
        # convert the frame to grayscale, and blur it
        frame = vs.read()
        frame = imutils.resize(frame, width=400)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)

        # grab the current timestamp and draw it on the frame
        timestamp = datetime.datetime.now()
        cv2.putText(frame, timestamp.strftime(
            "%A %d %B %Y %I:%M:%S%p"), (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        # if the total number of frames has reached a sufficient
        # number to construct a reasonable background model, then
        # continue to process the frame
        if total > frameCount:
            # detect motion in the image
            motion = md.detect(gray)

            # cehck to see if motion was found in the frame
            if motion is not None:
                # unpack the tuple and draw the box surrounding the
                # "motion area" on the output frame
                (thresh, (minX, minY, maxX, maxY)) = motion
                cv2.rectangle(frame, (minX, minY), (maxX, maxY),
                              (0, 0, 255), 2)

        # update the background model and increment the total number
        # of frames read thus far
        md.update(gray)
        total += 1

        # acquire the lock, set the output frame, and release the>>>>>>> HEAD: application.py

        # lock
        with lock:
            outputFrame = frame.copy()


def generate():
    # grab global references to the output frame and lock variables
    global outputFrame, lock

    # loop over frames from the output stream
    while True:
        # wait until the lock is acquired
        with lock:
            # check if the output frame is available, otherwise skip
            # the iteration of the loop
            if outputFrame is None:
                continue

            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)

            # ensure the frame was successfully encoded
            if not flag:
                continue

        # yield the output frame in the byte format
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
              bytearray(encodedImage) + b'\r\n')


@application.route("/video_feed")
def video_feed():
    # return the response generated along with the specific media
    # type (mime type)
    return Response(generate(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# Register
@application.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm(request.form)

    if request.method == "POST" and form.validate():
        name = form.name.data
        username = form.username.data
        email = form.email.data

        password = sha256_crypt.hash(form.password.data)

        cur = mysql.connection.cursor()
        mysql.set_character_set('utf8')
        cur.execute('SET NAMES utf8;')
        cur.execute('SET CHARACTER SET utf8;')
        cur.execute('SET character_set_connection=utf8;')

        sorgu = "INSERT INTO users (name,email,username,password) VALUES (%s,%s,%s,%s)"

        cur.execute(sorgu, (name, email, username, password))
        mysql.connection.commit()
        cur.close()
        flash("You have succesfully registered", "success")
        return redirect(url_for("index"))
    else:
        return render_template("register.html", form=form)


# Login
@application.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm(request.form)

    if request.form == "POST":
        username = form.username.data
        password_entered = form.password.data

        cur = mysql.connection.cursor()
        sorgu = "Select * from users where 'username' = %s"
        result = cur.execute(sorgu, (username))

        if result > 0:
            data = cur.fetchone()
            real_password = data["password"]
            if sha256_crypt.verify(password_entered, real_password):
                flash("Başarıyla giriş yapıldı", "succes")

                session["logged_in"] = True
                session["username"] = username

                return redirect(url_for("/"))
            else:
                flash("Parolanızı yanlış girdiniz", "danger")
                return redirect(url_for("login"))
        else:
            flash("Böyle bir kullanıcı yok", "danger")
            return redirect(url_for("login"))
    return render_template("login.html", form=form)

#   Logout
@application.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # construct the argument parser and parse command line arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--ip", type=str, required=True,
                    help="ip address of the device")
    ap.add_argument("-o", "--port", type=int, required=True,
                    help="ephemeral port number of the server (1024 to 65535)")
    ap.add_argument("-f", "--frame-count", type=int, default=32,
                    help="# of frames used to construct the background model")
    args = vars(ap.parse_args())

    # start a thread that will perform motion detection
    t = threading.Thread(target=detect_motion, args=(
        args["frame_count"],))
    t.daemon = True
    t.start()

    # start the flask app
    application.run(host=args["ip"], port=args["port"], debug=True,
                    threaded=True, use_reloader=False)

# release the video stream pointer
vs.stop()
