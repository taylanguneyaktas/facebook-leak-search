import requests
from bs4 import BeautifulSoup
from prettytable import PrettyTable
import json
import csv
import time

"""
	Facebook 2021 Leak Search
	Author: @curosim

	About the script:
	I must admit it looks a little too complicated for what it does, but keep in mind the script was written for interactive usage.
	The captcha on the website is lovely - because of that and out of respect for the service operator, it's implemented in the script instead of solved automatically.
"""

# CONFIG #################
config = {
	# URL of the Onion service
	'url':'4wbwa6vcpvcr3vvf4qkhppgy56urmjcj2vagu2iqgp3z656xcmfdbiqd.onion',

	# Tor socks proxy ports
	'tor_socks_proxy_ports':[9050, 9150],

	# Connectivity Check text
	'connectivity_check_text':'<title>Fuck Facebook (TM)</title>',

	# To find the captcha box, we search the HTML for the style attribute with following content.
	'captcha_style':'border: 1px solid black;display: inline-block;margin: 0px; padding:0px;',
	
	# Text which is shown on the page if a captcha is present
	'captcha_present_text':'fill in captcha!',

	# Results table style attribute content
	'results_table_style':'min-width: 50%',

	# Data Export Path
	'data_export_path':'./exports/'
}
##########################


def get_tor_session(port):
	""" Returns a requests session with the tor service set as socks proxy.
	"""
	session = requests.session()

	# It's important to use the protocol 'socks5h' in order to enable remote DNS resolving
	session.proxies['http'] = 'socks5h://localhost:{0}'.format(port)
	session.proxies['https'] = 'socks5h://localhost:{0}'.format(port)
	return session

class FacebookLeakSearch():
	authentication_id = None

	def __init__(self, onion_address):
		self.hidden_service_url = 'http://{0}'.format(onion_address)

	def set_tor_session(self, port):
		""" Create requests session with TOR as proxy.
		"""
		self.session = get_tor_session(port)

	def connectivity_check(self):
		""" Check if TOR proxy works and the hidden service is up and running.
		"""
		for port in config['tor_socks_proxy_ports']:
			self.set_tor_session(port)
			if self.is_onion_reachable():
				print("[*] TOR running (Local Port: {0}) and hidden service reachable.".format(port))
				return True
		return False

	def is_onion_reachable(self):
		""" Make request to hidden service to see if it's working.
		"""
		try:
			resp = self.session.get(self.hidden_service_url)
			if config['connectivity_check_text'] in resp.text: return True
		except: pass
		return False

	def initial_request(self):
		""" Simply for the first request in order to get the page source for the captcha.
		"""
		resp = self.session.get(self.hidden_service_url)
		return resp.text

	def is_captcha_present(self, source):
		""" Checks if the captcha is present in the HTML source.
		"""
		if config['captcha_present_text'] in source:
			return True
		else:
			return False

	def extract_captcha_from_source(self, source):
		""" The HTML source gets passed and the captcha text + hidden key will be extracted from it.
		"""
		soup = BeautifulSoup(source, 'html.parser')
		captcha_text = soup.find('pre', attrs={'style':config['captcha_style']}).text
		hidden_key = soup.find('input', attrs={'type':'hidden','name':'id'}).get('value')
		return captcha_text, hidden_key

	def solve_captcha(self, captcha_text, hidden_key):
		""" Solve the captcha (Send solution to server).
		"""
		
		data = {
			'captcha': captcha_text,
			'id': hidden_key
		}

		url = self.hidden_service_url+'/captcha'
		resp = self.session.post(url, data=data, allow_redirects=False)

		# If the captcha was correct, we get redirected to another URL
		# The new URL will be the same domain, but with a GET parameter 's' which acts as an identifier that we solved the captcha.
		# All further requests must be made with the s parameter set, otherwise the captcha will show up again.
		if resp.status_code == 302:
			# Here we extract the ID from the response header
			self.authentication_id = resp.headers['Location'].split('?s=')[1]
			return True
		else:
			return False

	def perform_search(self, user_id, first_name, last_name, phone_number, work, location, relationship_status='*any*', gender='*any*'):
		params = {
			's':self.authentication_id,
			'i':user_id, # ID
			'f':first_name, # firstname
			'l':last_name, # lastname
			't':phone_number, # phone number
			'w':work, # work
			'o':location, # location
			'r':relationship_status, # relationship status
			'g':gender  # gender
		}
		url = self.hidden_service_url+'/search'
		resp = self.session.post(url, params=params, allow_redirects=False)
		
		return self.parse_results_table(resp.text)

	def parse_results_table(self, source):
		""" Parse HTML and extract the results from the <table> rows.
		"""

		results = []
		soup = BeautifulSoup(source, 'html.parser')
		
		# get the table with the results
		table_rows = soup.find_all('tr')

		for row in table_rows[1:]:
			tds = row.find_all('td')

			entry = {}
			entry['user_id'] = tds[0].text
			entry['phone_number'] = tds[1].text
			entry['first_name'] = tds[2].text
			entry['last_name'] = tds[3].text
			entry['gender'] = tds[4].text
			entry['relationship_status'] = tds[5].text
			entry['work'] = tds[6].text
			entry['hometown'] = tds[7].text
			entry['location'] = tds[8].text
			entry['country'] = tds[9].text
			results.append(entry)

		return results

class CommandLineInterface():

	def __init__(self, fls):
		self.fls = fls

	def ask_for_captcha_solution(self, source=None):
		""" Ask the user to solve the captcha.
			It's a recursive function, in case the captcha solution is wrong.
		"""

		if source is None:
			print('[!] To use the service, you have to solve a captcha first.')
			source = self.fls.initial_request()

		captcha_text, hidden_key = self.fls.extract_captcha_from_source(source)
		print(captcha_text)
		captcha_solution = input('[*] Enter the letters: ')
		print("[*] Submitting captcha solution '{0}'".format(captcha_solution))
		if self.fls.solve_captcha(captcha_solution, hidden_key) == True:
			print("[*] Captcha correct! (Auth ID: {0})".format(self.fls.authentication_id))
		else:
			print("[!] The captcha solution was wrong! Try again.")
			self.ask_for_captcha_solution()

	def ask_for_search_params(self):
		""" Ask the user for search parameters.
		"""

		print("[*] Please enter the search criteria (Leave blank if not needed):")
		user_id = input("  > User ID: ")
		first_name = input("  > First Name: ")
		last_name = input("  > Last Name: ")
		phone_number = input("  > Phone Number: ")
		work = input("  > Work: ")
		location = input("  > Location: ")
		#relationship_status = input("[*] Relationship Status: ")
		#gender = input("[*] Gender: ")

		return (user_id, first_name, last_name, phone_number, work, location)

	def present_results(self, search_results):
		""" Displays the search results in a pretty CLI table :)
		"""

		if len(search_results) == 0:
			print("[!] The search was successful but it returned 0 results :(")
		else:
			print("[*] Success! {0} results have been found!".format(len(search_results)))
			results_table = PrettyTable()
			results_table.field_names = ["User ID", "Phone", "Name", "Lastname", "Gender", "Work", "Hometown", "Location", "Country"]
			results_table.align = 'l'

			for result in search_results:
				results_table.add_row(
					[
						result['user_id'],
						result['phone_number'],
						result['first_name'],
						result['last_name'],
						result['gender'],
						result['work'],
						result['hometown'],
						result['location'],
						result['country']
					]
				)

			print(results_table)

	def ask_how_to_continue(self, search_results):
		""" Ask the user how he would like to continue after the search.
		"""

		print("[*] How would you like to continue?")
		print("    1 - Export results")
		print("    2 - Search again")
		print("    3 - Quit")
		choice = input("[*] Enter your choice: ")

		if choice == '1':
			self.export_results(search_results)
		elif choice == '2':
			pass
		elif choice == '3':
			quit()
		else:
			print("[*] Please choose one of the options :)")
			self.ask_how_to_continue(search_results)

	def export_results(self, search_results):
		""" Ask the user how he wants to export the search results.
		"""

		print("[*] In which format you want to export the results?")
		print("    1 - JSON")
		print("    2 - CSV")
		choice = input("[*] Enter your choice: ")

		# Appendix for files so we dont overwrite previous files...
		timestamp = int(time.time())

		if choice == '1':
			filename = '{0}fbls_{1}.json'.format(config['data_export_path'], timestamp)
			with open(filename, 'w') as f:
				f.write(json.dumps(search_results, indent=4, sort_keys=True))
			print("[*] Exported {0} results as JSON (Filename: {1})".format(len(search_results), filename))
		elif choice == '2':
			filename = '{0}fbls_{1}.csv'.format(config['data_export_path'], timestamp)
			keys = list(search_results[0].keys())
			with open(filename, 'w') as f:
				w = csv.DictWriter(f, keys)
				w.writeheader()
				for search_result in search_results:
					w.writerow(search_result)
			print("[*] Exported {0} results as CSV (Filename: {1})".format(len(search_results), filename))
		else:
			print("[*] Please choose one of the options :)")
			self.export_results(search_results)


def quit():
	print("[*] Quitting FBLS")
	exit()

def banner():
	print(" ________  ______   _____      ______   ")
	print("|_   __  ||_   _ \\ |_   _|   .' ____ \\  ")
	print("  | |_ \\_|  | |_) |  | |     | (___ \\_| ")
	print("  |  _|     |  __'.  | |   _  _.____`.  ")
	print(" _| |_     _| |__) |_| |__/ || \\____) |")
	print("|_____|   |_______/|________| \\______.'")
	print()
	print("Facebook Leak Search - CLI Wrapper for the hidden service \"Fuck Facebook (TM)\"")
	print("Author of the CLI Wrapper: @curosim")
	print()

def main():
	banner()

	fls = FacebookLeakSearch(config['url'])
	cli = CommandLineInterface(fls=fls)

	if fls.connectivity_check() == False:
		print("[!] Tor not working or hidden service not reachable (Local Tor ports tried: {0})".format(config['tor_socks_proxy_ports']))
	else:
		cli.ask_for_captcha_solution()

		while True:
			search_params = cli.ask_for_search_params()

			print("[*] Performing 'API' Search")
			search_results = fls.perform_search(*search_params)

			cli.present_results(search_results)
			if len(search_results) > 0:
				cli.ask_how_to_continue(search_results)


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		print()
		print("[!] Execution interrupted with keyboard...")
		quit()