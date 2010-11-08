#!/usr/bin/python

import urllib
import pycurl
import StringIO
import sys
import os
import getpass
from lxml import html

__author__ = "dave bl. db@d1b.org"
__version__= "0.1"
__license__= "gpl v2"
__program__ = "mq blackboard downloader"


def get_input():
	return str (raw_input() )

def map_page_content_to_link_id(data, only_get_sub_content_pages=False):
	dict_l = {}
	doc = html.fromstring(data)
	for x in doc.xpath("//div[@class='orgtext']/a"):
		if not only_get_sub_content_pages:
			dict_l[x.text.replace("\n", "")] = str(x.attrib['href']).split("'")[1]

		elif "ORGANIZER_PAGE_TYPE" in str(x.attrib['href']):
			dict_l[x.getparent().text_content().replace("\n", "")] = str(x.attrib['href']).split("'")[1]
	return dict_l

def get_user_credentials_from_user_input(conn_details):
	#get username / password
	print "enter your username "
	conn_details["username"] = get_input()
	conn_details["password"] = getpass.getpass("enter your password\n")
	return conn_details

def get_blackboard_stuff(url_login, url_course_base, conn_details):
	url_student_base_page = url_course_base + "/studentCourseView.dowebct"

	submit_data_t = [ ("glcid", "URN:X-WEBCT-VISTA-V1:7249d2a7-817f-8407-004b-c336a20fac36"), ("gotoid", "null"), ("insId", "5122001"), ("insName", "Macquarie University")  , ('password', conn_details["password"]), ("timeZoneOffset", "-10") ,('webctid', conn_details["username"])  ]

	submit_data_t = urllib.urlencode(submit_data_t)

	string_s = StringIO.StringIO()
	connection = pycurl.Curl()
	connection.setopt(pycurl.FOLLOWLOCATION, True)
	connection.setopt(pycurl.SSL_VERIFYPEER, 1)
	connection.setopt(pycurl.SSL_VERIFYHOST, 2)
	connection.setopt(pycurl.WRITEFUNCTION, string_s.write)
	connection.setopt(pycurl.COOKIEFILE, os.path.expanduser("~/.mq/b_cookie") )
	connection.setopt(pycurl.COOKIEJAR, os.path.expanduser("~/.mq/b_cookie") )
	connection.setopt(pycurl.POSTFIELDS, submit_data_t)
	connection.setopt(pycurl.URL, url_login)
	#log in
	connection.perform()

	#from the main page for the unit -> fetch the links now
	connection.setopt(pycurl.WRITEFUNCTION, string_s.write)
	connection.setopt(pycurl.URL, url_student_base_page)
	connection.perform()
	the_page = str(string_s.getvalue())
	dict_course_content_links = map_page_content_to_link_id(the_page)

	make_folder("download", True)
	use_connection_traverse_course_links(url_student_base_page, connection, dict_course_content_links)

	#close the connection
	connection.close()

	return the_page

def get_content_from_connection(connection, url, return_headers=False):
	string_s = StringIO.StringIO()
	header = StringIO.StringIO()
	connection.setopt(pycurl.FOLLOWLOCATION, True)
	connection.setopt(pycurl.WRITEFUNCTION, string_s.write)
	connection.setopt(pycurl.HEADERFUNCTION, header.write)
	connection.setopt(pycurl.URL, url)
	connection.perform()

	the_page = str(string_s.getvalue())
	header_data = str(header.getvalue())
	if return_headers:
		return the_page, header_data
	return the_page


def use_connection_traverse_course_links(url_student_base_page, connection, dict_course_content_links):
	display_url_path = "?displayinfo="

	for link_name, item_id in dict_course_content_links.items():
		safe_link_name = replace_f_name_with_safer_version(link_name)

		the_page = get_content_from_connection(connection, url_student_base_page + display_url_path + item_id)


		child_content_pages =  map_page_content_to_link_id(the_page, True)
		if len(child_content_pages.keys() ) > 0:
			# go through all children content pages
			use_connection_traverse_course_links(url_student_base_page, connection, child_content_pages)

		container_link_d = map_page_content_to_link_id(the_page)

		download_course_files(url_student_base_page, connection, container_link_d, safe_link_name)

def download_course_files(url_student_base_page, connection, container_link_d, folder_name):
	safe_folder_name = replace_f_name_with_safer_version(folder_name)
	make_folder(safe_folder_name)
	# remove the extra path added in use_connection_traverse_course_links
	url_student_base_page = url_student_base_page.replace("/studentCourseView.dowebct", "")

	dl_url_path = "/displayContentPage.dowebct?pageID="
	blackboard_base_url = "http://learn.mq.edu.au"
	for raw_name, item_id in container_link_d.items():

		the_page = get_content_from_connection(connection, url_student_base_page + dl_url_path + item_id)
		try:
			the_real_item_url = get_actual_file_dl_location(the_page)

			the_page, headers = get_content_from_connection(connection, blackboard_base_url + the_real_item_url, True)
			unsafe_file_name = get_file_name_from_header(headers)
			if unsafe_file_name != "":
				safe_file_name = replace_f_name_with_safer_version(unsafe_file_name)
			else:
				safe_file_name = replace_f_name_with_safer_version(raw_name)
			print safe_file_name

			write_downloaded_content_to_file(the_page, safe_folder_name + "/" + safe_file_name)
		except Exception, e:
			pass


def get_file_name_from_header(headers):
	unsafe_file_name = ""
	for line in headers.split("\n"):
		if "filename" in line:
			try:
				unsafe_file_name = urllib.unquote_plus( str(line.split('"')[1]) )

				break
			except:
				pass
	return unsafe_file_name


def get_actual_file_dl_location(data):
	doc = html.fromstring(data)
	return [str(x.text).split('"')[1] for x in doc.xpath("//script")][0]

def make_folder(folder_name, init=False):
	DLFOLDER = "download/"
	safe_f_name = replace_f_name_with_safer_version(folder_name)
	try:
		if init:
			os.mkdir(safe_f_name)
		else:
			os.mkdir(DLFOLDER + safe_f_name)
	except Exception, e:
		print e


def replace_f_name_with_safer_version(name):
	name = name.replace("/", "_")
	name = name.replace(" ", "_")
	name = name.replace("..", "_")
	name = name.replace("\"", "_")
	name = name.replace("~", "_")
	name = name.replace('"', "_")
	name = name.replace("'", "_")
	name = name.replace(".py", "_python")
	name = name[0:223]
	return name

def delete_cookie():
	try:
		os.remove(os.path.expanduser("~/.mq/b_cookie") )
	except:
		print "failed to remove the cookie file " + str (os.path.expanduser("~/.mq/b_cookie") )

def create_mq_directory(mq_dir):
	#if the paths don't exist already, create them.
	state = "done"
	if mq_dir is None:
		mq_dir = os.path.expanduser("~/.mq")
	if not os.path.exists(mq_dir):
		state = "init"
		os.mkdir(mq_dir)
	os.chmod(mq_dir, 16832)
	return state

def write_downloaded_content_to_file(data, full_file_loc):
	DLFOLDER = "download/"
	write_to_a_file(data, DLFOLDER + full_file_loc)


def write_to_a_file(data, full_file_loc):
	the_file = open(full_file_loc, 'w')
	the_file.write(data)
	the_file.close()

def read_from_a_file(full_file_loc,return_type ):
	the_file = open(full_file_loc, 'r')
	if return_type == "read":
		return_type = the_file.read()
	else:
		return_type = the_file.readlines()
	the_file.close()
	return return_type

def save_credentials_to_accounts_file(username,password,file_loc):
	assert username !=""
	assert password !=""
	write_to_a_file("username="+username +"\n" +"password="+password+"\n", file_loc)

def get_credentials_from_accounts_file(conn_details):
	account_file_loc = os.path.expanduser("~/.mq/b_account")
	credentials =[]
	username = ""
	password = ""

	the_file = read_from_a_file(account_file_loc, "readlines")
	for line in the_file:
		if "username=" in line:
			index = line.find("=")
			assert index +1 < len(line)
			username = line[index+1:-1]
		if "password=" in line:
			index = line.find("=")
			assert index +1 < len(line)
			password = line[index+1:-1]
	conn_details["username"] = username
	conn_details["password"] = password
	return conn_details

def main(url_course_base):

	url_login = "https://learn.mq.edu.au/webct/authenticateUser.dowebct"
	conn_details = {}
	data = ""

	state = create_mq_directory(None)
	if state == "init":
		conn_details = get_user_credentials_from_user_input(conn_details)
		save_credentials_to_accounts_file(conn_details["username"], conn_details["password"], os.path.expanduser("~/.mq/b_account") )
	#get credentials
	conn_details = get_credentials_from_accounts_file(conn_details)
	data = get_blackboard_stuff(url_login, url_course_base, conn_details)

	delete_cookie()

if __name__=='__main__':
	url_course_base = "http://learn.mq.edu.au/webct/urw/lc11968212159011.tp11968212181011"
	main(url_course_base)
