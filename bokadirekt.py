import yaml
import smtplib
import argparse
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import pdb
import re

# Function to send an email
def send_email(subject, body):
    global email_config
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = email_config['sender']
    msg['To'] = email_config['receiver']

    try:
        server = smtplib.SMTP(email_config['smtp_host'], email_config['smtp_port'])
        server.starttls()
        server.login(email_config['sender'], email_config['password'])
        server.send_message(msg)  # send_message allows passing the EmailMessage directly
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

# Load seen slots from a YAML file
def load_seen_slots(filename):
    try:
        with open(filename, 'r') as f:
            return set(yaml.load(f, Loader=yaml.FullLoader) or [])
    except FileNotFoundError:
        return set()

# Write seen slots to a YAML file
def save_seen_slots(filename, seen_slots):
    with open(filename, 'w') as f:
        yaml.dump(list(seen_slots), f)

# Function to check for new time slots
def check_for_slots(driver, seen_slots, filename):
    # Logic to fetch the list of time slots from the page


    # This will wait up to 10 seconds for the element to be clickable
    # before attempting to click.
    try:
        # Find the button with the text "Tillåt alla cookies"
        # The XPath uses "normalize-space()" function to trim leading/trailing whitespace
        # and handle cases where the text has multiple lines or non-breaking spaces.
        cookie_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Tillåt alla cookies']"))
        )
        cookie_button.click()
    except Exception as e:
        print(f"Error: {e}")

    time.sleep(5)

    # see if there is a message about no available time slots this week
    no_time_slots = driver.find_elements(By.XPATH, "//span[@class='firstday']//span")

    # if there is a message about no available time slots this week
    if no_time_slots:
        # check if the next time slos has been seen before
        if no_time_slots[1].text not in seen_slots:
            # add the next time slot to the seen slots
            seen_slots.add(no_time_slots[1].text)
            # save the seen slots
            save_seen_slots(filename, seen_slots)
            # send an email
            send_email(f"Ny tid släppt: {no_time_slots[1].text}", f"Ny tid har släppts på bokningssidan. {driver.current_url}")
            return
        else:
            # if the next time slot has been seen before, return
            print("No new time slots")
            return


    ## if there are times this week, find the week number and the available time slot

    # Find spans that contain the text "Vecka"
    week_span = driver.find_element(By.XPATH, "//span[contains(., 'Vecka ')]")

    # Assuming span.text is something like "Blah Vecka 47 blah"
    text = week_span.text

    # Use a regular expression to match "Vecka" followed by a space and then the number
    match = re.search(r'VECKA (\d+)', text)

    # Check if we found a match
    if match:
        # The first group (1) captures the number part of the match
        week_number = match.group(1)

        # Convert the captured number to an integer if necessary
        week_number = int(week_number)
    else:
        raise ValueError("Week number not found")

    # Find the parent div container
    parent_div = driver.find_element(By.XPATH, "//div[@class='hours sticky']")

    # Find all day div elements within the parent container
    days_divs = parent_div.find_elements(By.CSS_SELECTOR, "div.border-black-100")
    
    # The days of the week, for reference (assuming Monday is the first day)
    days_of_week = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]

    # Iterate through the day divs and find the ones that contain the time slots
    new_slots = set()
    for index, day_div in enumerate(days_divs):
        time_slots = day_div.find_elements(By.CSS_SELECTOR, "[data-cy='weekPickerTimeslot']")
        if time_slots:
            # There is at least one time slot available on this day
            day_name = days_of_week[index]
            print(f"Found available time on {day_name}")
            for time_slot in time_slots:
                # Assuming the first span contains the time vale
                time_value = time_slot.find_element(By.TAG_NAME, "span").text
                slot_id = f"{week_number}-{day_name}-{time_value}"
                print(f"Time available: {time_value}")
                if slot_id not in seen_slots:
                    new_slots.add(slot_id)
                    seen_slots.add(slot_id)
                    print(f"Not seen before: {slot_id}")
                else:
                    print(f"Already seen: {slot_id}")


    # If new slots are detected, update the file and send an email
    if new_slots:
        save_seen_slots(filename, seen_slots)
        send_email(f"Ny tid släppt: {', '.join([ f'v{slot}' for slot in new_slots ])}", f"Ny tid har släppts på bokningssidan. {driver.current_url}")



# Process command line arguments
parser = argparse.ArgumentParser(description="Monitor barber booking page for new time slots.")
parser.add_argument('-c', '--config', type=str, required=True, help='Path to the YAML configuration file.')
parser.add_argument('-u', '--url', type=str, help='Override the URL in the config file (optional).')
args = parser.parse_args()

# Load the configuration from a YAML file
with open(args.config, 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

# If a URL is given in arguments, override the YAML configuration
url = args.url if args.url else config['url']

# Remaining configuration
email_config = config['email']

# Path to your YAML file that contains seen slots
yaml_filename = 'seen_slots.yaml'

# Load seen slots before starting the monitoring loop
seen_slots = load_seen_slots(yaml_filename)

geckodriver_path = './geckodriver'  # Replace with your GeckoDriver path

firefox_options = Options()
firefox_options.add_argument('--headless')

service = FirefoxService(executable_path=geckodriver_path)
driver = webdriver.Firefox(service=service, options=firefox_options)

driver.get(url)

check_for_slots(driver, seen_slots, yaml_filename)

driver.quit()

