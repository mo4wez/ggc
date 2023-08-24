from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from config import GolestanGradeCheckerConfig
from time import sleep
import logging
import re
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
    )
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
    )



class GolestanGradeChecker:
    def __init__(self):
        self.config = GolestanGradeCheckerConfig()
        self.driver = None
        self.term_no = None
        self.captcha_code = None
        self.student_name = None
        self.token = self.config.token
        self.bot = Application.builder().token(self.token).build()
        self.START, self.USERNAME, self.PASSWORD, self.TERM, self.CAPTCHA = range(5)

    def run(self):

        # Configure logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )

        self.bot.add_handler(ConversationHandler(
            entry_points=[CommandHandler("start", self.start_message)],
            states={
                self.START: [MessageHandler(filters.TEXT, self.start)],
                self.USERNAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), self._get_username)],
                self.PASSWORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), self._get_password)],
                self.TERM: [MessageHandler(filters.TEXT & (~filters.COMMAND), self._get_term_number)],
                self.CAPTCHA: [MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_captcha)]
            },
            fallbacks=[
                CommandHandler(command="cancel", callback=self.cancel, filters=filters.COMMAND),
                CommandHandler("start", self.start_message)
            ]
        ))

        self.bot.add_handler(CallbackQueryHandler(callback=self._go_to_next_term, pattern='next_term'))
        self.bot.add_handler(CallbackQueryHandler(callback=self._go_to_previous_term, pattern='previous_term'))
        self.bot.add_error_handler(self.error)

        self.bot.run_polling()

    async def start_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('Received /start command')
        message = update.message.text

        keyboard = [
            ['شروع'],
            ['وارد کردن دستی لینک سامانه']
        ]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="سلام خوش اومدی رفیق 😌\n\nکافیه دکمه شروع رو بزنی تا بریم سامانه گلستان رو زیر و رو کنیم 😎🤪",
                                      reply_markup=markup)
        return self.START

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in start func')
        reply_markup = ReplyKeyboardRemove()
        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="خب الان باید شماره دانشجویی خودتو برام بفرستی تا بتونم وارد سیستم گلستان بشم😃\n\nدر ضمن میدونی که مرحله بعد ازت رمز سامانه رو میخام پس آماده کن پسوردتو",
                                      reply_markup=reply_markup)
        logging.info(f"user {update.message.chat.id} ({update.message.chat.username}) sends: {update.message.text}")
        self.driver = self._setup_driver()
        return self.USERNAME

    async def _get_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in get_username func')
        logging.info(f"user {update.message.chat.id} ({update.message.chat.username}) sends: {update.message.text}")
        username = update.message.text
        context.user_data['username'] = username
        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="خب...\n\nالان رمز سامانه‌تو بفرست! ممکنه کد ملیت باشه اگه یادت نیست😉")
        return self.PASSWORD

    async def _get_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in get_password func')
        logging.info(f"user {update.message.chat.id} ({update.message.chat.username}) sends: {update.message.text}")
        password = update.message.text
        context.user_data['password'] = password
        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="میخای نمره های ترم چندت رو ببینی؟ عدد ترم رو وارد کن\n\nمثلا: 1")

        return self.TERM

    async def _get_term_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in get_term_number func')
        logging.info(f"user {update.message.chat.id} ({update.message.chat.username}) sends: {update.message.text}")
        term_number = update.message.text
        context.user_data['term_no'] = term_number
        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="خب یه سی ثانیه صبر کن تا کد کپچا رو بفرستم برات...")
        await self._login_to_golestan(update, context)
        try:
            await context.bot.sendPhoto(
                chat_id=update.effective_chat.id,
                photo=open(file=rf'C:\Users\moawezz\Desktop\golestan\captchas\cap-{update.effective_chat.id}.png',
                           mode='rb'),
                caption='کد توی عکس رو ببین و با دقت برام بفرستش\n\nچون هنوز قابلیت تشخیص درست یا غلط بودن کد برام تعریف نشده😢'
            )
        except:
            pass

        return self.CAPTCHA

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        self.driver.quit()
        print("ConversationHandler.END")
        await update.message.reply_text("عملیات لغو شد، مجدد ربات رو استارت کن.")
        return ConversationHandler.END

    def _setup_driver(self):
        logging.info('in Setup driver')
        options = Options()
        excluded_url = 'https://education.cfu.ac.ir/forms/authenticateuser/main.htm'
        options.add_argument(f"--no-proxy-server={excluded_url}")
        options.add_argument("--headless=new")  # run in headless mode (without gui)
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        return driver

    def _switch_to_main_frame(self, faci_id):
        frame_names = (f'Faci{str(faci_id)}', 'Master', 'Form_Body')
        for name in frame_names:
            frame = self.driver.find_element(By.NAME, name)
            logging.info(f'switch to {frame.tag_name}')
            self.driver.switch_to.frame(frame)

    async def _login_to_golestan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('login to golestan')
        sleep(3)
        self.driver.get(self.config.login_url)
        self._switch_to_main_frame(1)
        sleep(6)

        try:
            username_field = self.driver.find_element(By.ID, 'F80351')
            username_field.send_keys(context.user_data['username'])

            password_field = self.driver.find_element(By.ID, 'F80401')
            password_field.send_keys(context.user_data['password'])

            captcha_field = self.driver.find_element(By.ID, 'F51701')
            login_button = self.driver.find_element(By.ID, 'btnLog')
            self._save_captcha_image(update, context)
        except Exception as e:
            print(e)
            return ConversationHandler.END

        # Store the captcha_field and login_button in user_data
        user_data = context.user_data
        user_data['captcha_field'] = captcha_field
        user_data['login_button'] = login_button

    async def _handle_captcha(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in handle_captcha func')
        captcha_code = update.message.text
        context.user_data['captcha_code'] = captcha_code
        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="یه دیقه منتظر بمون تا نمره هاتو برات ارسال کنم...😃")

        # Access the stored values from user_data
        username = context.user_data['username']
        password = context.user_data['password']
        user_data = context.user_data
        captcha_code = context.user_data['captcha_code']
        await self._handle_captcha_solution(update, context)

    async def _handle_captcha_solution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in handle_captcha_solution')
        self.captcha_code = update.message.text
        print(f'Captcha code: {self.captcha_code}')

        # Retrieve the user data to access the captcha field and submit button
        user_data = context.user_data
        captcha_field = user_data['captcha_field']
        login_button = user_data['login_button']

        captcha_field.send_keys(context.user_data['captcha_code'])
        login_button.click()
        sleep(3)
        await self._send_information_to_bot(update, context)

    def _get_student_name(self):
        student = self.driver.find_element(By.XPATH, """.//*[@id="_mt_usr"]""").get_attribute("innerText")
        pattern = r":(.*?)\s+خروج"
        match = re.search(pattern, student)

        if match:
            self.student_name = match.group(1).strip()

    def _go_to_etelaate_jame_daneshjoo_page(self):
        logging.info('going to etelaate_jame_daneshjoo_page')
        self._get_student_name()
        self._switch_to_main_frame(2)
        sleep(4)
        student_full_info = self.driver.find_element(By.XPATH, '//*[@id="mendiv"]/table/tbody/tr[6]/td')
        for _ in range(0, 2): student_full_info.click()
        sleep(3)

    def _go_to_semester(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('Going to semester...')
        user_data = context.user_data
        self.driver.switch_to.default_content()
        self._switch_to_main_frame(3)

        terms_status_table = self.driver.find_element(By.XPATH, """//table[@id="T01"]""")
        term_field = terms_status_table.find_element(By.XPATH,
                                                     f"""//tr[@class="TableDataRow"][{user_data['term_no']}]/td[1]""")
        term_field.click()
        sleep(2)
        self.driver.switch_to.frame('FrameNewForm')

    def _find_term_status(self):
        status = {}
        logging.info('finding term status')

        sleep(2)
        status_table = self.driver.find_element(By.XPATH, """.//table[@id="T01"]""")
        table_body = status_table.find_element(By.XPATH, """.//tbody""")
        term_rows = table_body.find_element(By.XPATH, """.//tr[3]""")
        total_rows = table_body.find_element(By.XPATH, """.//tr[5]""")

        status['student'] = self.driver.find_element(By.XPATH, """.//*[@id="F51851"]""").text
        status['term_description'] = self.driver.find_element(By.XPATH, """.//*[@id="F57551"]""").text
        status['term_number'] = self.driver.find_element(By.XPATH, """.//*[@id="F43501"]""").text
        status['failure'] = self.driver.find_element(By.XPATH, """.//*[@id="F44151"]""").text
        status['term_average'] = term_rows.find_element(By.XPATH, """.//td[2]""").text
        status['passed_in_term'] = term_rows.find_element(By.XPATH, """.//td[3]""").text
        status['get_in_term'] = term_rows.find_element(By.XPATH, """.//td[4]""").text
        status['failed_in_term'] = term_rows.find_element(By.XPATH, """.//td[5]""").text
        status['total_average'] = total_rows.find_element(By.XPATH, """.//td[2]""").text
        status['total_passed'] = total_rows.find_element(By.XPATH, """.//td[3]""").text

        return status

    def _find_term_grades(self):
        result = {}
        logging.info('finding term grades')
        sleep(2)
        grades_table = self.driver.find_element(By.XPATH, """.//table[@id="T02"]""")
        grades_table = grades_table.find_element(By.XPATH, """.//tbody""")
        grades_rows = grades_table.find_elements(By.XPATH, """.//tr[@class="TableDataRow"]""")

        for row in grades_rows:
            course_name = row.find_element(By.XPATH, """.//td[6]""").get_attribute("title")
            grade_element = row.find_element(By.XPATH, """.//td[9]""")
            course_grade = grade_element.find_element(By.XPATH, """.//nobr[1]""").text
            # course_result = row.find_element(By.XPATH, """.//td[10]""").get_attribute("title")

            if course_grade == "":
                course_grade = 'بدون نمره'
            else:
                course_grade = course_grade

            sleep(1)
            if course_grade:
                result[course_name] = course_grade

        return result

    async def _send_information_to_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in _send_information_to_bot')
        sleep(3)
        self.driver.switch_to.default_content()
        sleep(1)
        self._go_to_etelaate_jame_daneshjoo_page()
        sleep(2)
        self._go_to_semester(update, context)
        sleep(2)
        await self._show_grades_in_bot(update, context)

    async def _show_grades_in_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info('in _show_grades_in_bot')
        user_data = context.user_data
        grades = self._find_term_grades()
        status = self._find_term_status()

        keyboard = [
            [InlineKeyboardButton(f'{status["term_description"]}', callback_data=1)],
            [InlineKeyboardButton(f'وضع مشروطی: {status["failure"]}', callback_data=1)],
            [InlineKeyboardButton(f'واحد اخذ شده ترم: {status["get_in_term"]}', callback_data=1)],
            [
                InlineKeyboardButton(f'واحد رد شده ترم: {status["failed_in_term"]}', callback_data=1),
                InlineKeyboardButton(f'واحد گذرانده ترم: {status["passed_in_term"]}', callback_data=1)
            ],
            [InlineKeyboardButton(f'واحد گذرانده کل: {status["total_passed"]}', callback_data=1)],
            [
                InlineKeyboardButton(f'معدل کل: {status["total_average"]}', callback_data=1),
                InlineKeyboardButton(f'معدل ترم: {status["term_average"]}', callback_data=1)
            ],
            [
                InlineKeyboardButton('ترم بعد ⬅️', callback_data='next_term'),
                InlineKeyboardButton('➡️ ترم قبل', callback_data='previous_term')
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the grades to the user
        if 'grades_message_id' in user_data:
            # Edit the previous message
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=user_data['grades_message_id'],
                text=f"اینم از نمره های درخشانت {self.student_name} عزیز \n\n" + "\n".join(
                    [f"{index + 1}- {course_name}: {course_grade}" for index, (course_name, course_grade) in
                     enumerate(grades.items())]),
                reply_markup=reply_markup
            )
        else:
            # Send a new message
            grades_message = await context.bot.sendMessage(
                chat_id=update.effective_chat.id,
                text=f"اینم از نمره های درخشانت {self.student_name} عزیز \n\n" + "\n".join(
                    [f"{index + 1}- {course_name}: {course_grade}" for index, (course_name, course_grade) in
                     enumerate(grades.items())]),
                reply_markup=reply_markup
            )
            # Store the message ID for future editing
            user_data['grades_message_id'] = grades_message.message_id

    async def _go_to_next_term(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query

        # Handle the case when the query object is None
        if query is None:
            return

        data = query.data
        if data == "next_term":
            logging.info('Going to next_term')
            next_term = self.driver.find_element(By.XPATH, """.//img[@title="ترم بعدي"]""")
            next_term.click()
            await self._show_grades_in_bot(update, context)

    async def _go_to_previous_term(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query

        # Handle the case when the query object is None
        if query is None:
            return

        data = query.data
        if data == "previous_term":
            logging.info('Going to previous_term')
            previous_term = self.driver.find_element(By.XPATH, """.//img[@title="ترم قبلي"]""")
            previous_term.click()
            await self._show_grades_in_bot(update, context)
            await  context.bot.sendMessage()

    def _save_captcha_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        captcha_image = self.driver.find_element(By.ID, 'imgCaptcha')
        captcha_image.screenshot(rf'C:\Users\moawezz\Desktop\golestan\captchas\cap-{update.effective_chat.id}.png')
        logging.info('captcha code saved')

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # log errors
        logging.error(f'caused error {context.error}')
        await context.bot.sendMessage(chat_id=update.effective_chat.id,
                                      text="❌ خطایی به وجود اومد، ربات رو مجدد استارت کن")
        self.driver.quit()
        return ConversationHandler.END

# moawezz - Aug 24 2023