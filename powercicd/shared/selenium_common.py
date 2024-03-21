import logging
import os
from selenium.webdriver.chromium.webdriver import ChromiumDriver
from selenium import webdriver


log = logging.getLogger(__name__)


_FILE_DIR         = os.path.dirname(os.path.abspath(__file__))
SELENIUM_LOG_PATH = os.path.normpath(os.path.abspath(fr"{_FILE_DIR}\..\.selenium\logs\selenium.log"))
USER_DATA_DIR     = os.path.normpath(os.path.abspath(fr"{_FILE_DIR}\..\.selenium\user_data"))


SELENIUM_PORT = 92220


def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def configure_selenium_logger():
    from selenium.webdriver.remote.remote_connection import LOGGER
    LOGGER.propagate = False
    
    log_dir = os.path.dirname(SELENIUM_LOG_PATH)
    log.info(f"Ensuring the log directory exists: '{log_dir}'")
    os.makedirs(log_dir, exist_ok=True)
    selenium_handler = logging.FileHandler(SELENIUM_LOG_PATH)
    selenium_handler.setLevel(logging.INFO)
    selenium_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    LOGGER.addHandler(selenium_handler)
    log.info(f"Configured the Selenium logger to write to '{SELENIUM_LOG_PATH}'")
    

def new_browser(tenant: str, keep_browser_open: bool) -> ChromiumDriver:
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    log.info(f"Opening new browser: {USER_DATA_DIR=}, {tenant=}")
    options = webdriver.EdgeOptions()
    options.add_argument(f'user-data-dir={USER_DATA_DIR}')
    options.add_argument(f"profile-directory={tenant}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--remote-debugging-port={SELENIUM_PORT}")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    if keep_browser_open:
        while is_port_in_use(SELENIUM_PORT):
            log.warning(f"Port {SELENIUM_PORT} is already in use. You have set the '--keep-browser-open' flag.")
            input("Close previous selenium windows and press Enter to continue...")        
        options.add_experimental_option("detach", True)
    
    return webdriver.Edge(options=options)
