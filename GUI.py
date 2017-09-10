import spotdl
import os
import subprocess
import glob
import json

from appJar import gui
from os.path import basename

# handle button events
def press(button):

	#getting current location
	curr_dir = os.getcwd()
	launcher_path = os.path.join(curr_dir,'spotdl.py')
	target_folder = os.path.join(curr_dir,'Music')
	print(target_folder)
	folder = app.getEntry("Folder")

	option = app.getOptionBox('Download Type')
	input_text = app.getEntry('Search')
	
	print('Download type -->')
	print(option)

	if button == "Shutdown":
		app.stop()
		command = 'rm meta.txt'
		os.system(command)

	elif button == "Add":
		add_to_file(option,input_text)

	else:
		#Download pressed
		if folder != "":
			target_folder = folder

		if len(input_text) > 0:
			add_to_file(option,input_text)

		#******* insert loop on file ******
		with open("meta.txt", "r") as meta_file:
			entries = meta_file.readlines()

	
		print(entries)

		for entry in entries:
			print('entry: '+ entry)
			option, input_text = entry.split("&&&")

			if(option == 'Song'):
				if input_text.find('https') == -1:
					input_text = '"' + input_text+ '"'
				command = 'python ' + launcher_path + ' --folder ' + target_folder +' --song ' + input_text
				print(command)
				process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

				process.wait()
				app.clearEntry("Search")

			elif(option == 'Playlist'):

				command = 'python ' + launcher_path +' --playlist ' + input_text
				process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
				process.wait()
				download_from_list(target_folder,curr_dir)


			elif(option == 'Username'):

				url, user_code = input_text.split("user/")
				target_folder = os.path.join(target_folder,user_code)
				command = 'mkdir ' + target_folder
				os.system(command)
				command = 'python ' + launcher_path +' --username ' + user_code
				os.system(command)
				download_from_list(target_folder,curr_dir)

			elif(option == 'Album'):
				
				command = 'python3 ' + curr_dir + 'spotdl.py -A ' + input_text
				os.system(command)

			else:
				print("Input Error")
			
		print('completed')

		#clean metadata
		command = 'rm meta.txt'
		os.system(command)

		app.bell()

def add_to_file(option,input_text):
	with open("meta.txt", "a") as meta_file:
		meta_file.write(option + "&&&" + input_text)
		meta_file.write('\n')

	meta_file.close()
	print('Added')
	app.clearEntry("Search")

def download_from_list(target_folder,curr_dir,folder_creation=True):
	target_folder = target_folder.split()

	for file in glob.glob("*.txt"):
		if file != 'LICENSE.txt' and file != 'requirements.txt' and file != 'meta.txt':
			print('Playlist file founded!')

			if folder_creation:
				print('Create playlist directory')
				folder_name = file.replace('.txt','')
				folder_name = folder_name.split()
				playlist_folder = os.path.join(target_folder[0],folder_name[0])
				command = 'mkdir ' + playlist_folder
				os.system(command)

			command = 'python ' + launcher_path +' --folder ' + playlist_folder + ' --list=' + file
			os.system(command)

			command = 'cd ..'
			os.system(command)
			#clear playist directory
			print('...removing...')
			print(file)
			command = 'rm  ' + os.path.join(curr_dir,file)
			
	app.clearEntry("Search")


# create a GUI variable called app
app = gui("Spotify Downloader", "400x200")
app.setBg("white")
app.setFont(16)
app.addDirectoryEntry("Folder")


# add & configure widgets - widgets get a name, to help referencing them later
app.addOptionBox("Download Type", ["Album","Playlist","Song","Username"])


app.addLabelEntry("Search")

# link the buttons to the function called press
app.addButtons(["Add", "Download", "Shutdown"], press)

app.setFocus("Search")


# start the GUI
app.go()

