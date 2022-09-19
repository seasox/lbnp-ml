FILTERED_SPEAKERS = [ 'Tim Pritlove', 'Linus Neumann' ]

CACHEDIR = 'cache'

def clean_dir(folder):
	import os, shutil
	if not os.path.exists(folder):
		return
	for filename in os.listdir(folder):
		file_path = os.path.join(folder, filename)
		try:
			if os.path.isfile(file_path) or os.path.islink(file_path):
				os.unlink(file_path)
			elif os.path.isdir(file_path):
				shutil.rmtree(file_path)
		except Exception as e:
			print('Failed to delete %s. Reason: %s' % (file_path, e))

def split_and_export_track(episode_title, audio, transcript, output_path='output', metadata_only=False, fmeta_lock=None):
	print('processing episode ' + episode_title)
	import os
	import webvtt
	import re
	from pydub import AudioSegment
	voice_cue = re.compile('^<v (.*)>')
	speaker_parts = {}
	speaker_audios = {}
	ignored_speakers = set()
	for caption in webvtt.read(transcript):
		speaker = voice_cue.search(caption.raw_text)[1]
		if speaker not in FILTERED_SPEAKERS:
			ignored_speakers.add(speaker)
			continue
		if speaker not in speaker_parts:
			speaker_parts[speaker] = [caption]
		else:
			speaker_parts[speaker] += [caption]
	if not metadata_only:
		print('loading and resampling ' + audio)
		sound = AudioSegment.from_file(audio)
		sound = sound.set_channels(1)\
		             .high_pass_filter(100)\
		             .low_pass_filter(7000)\
		             .set_frame_rate(22050)
		print('done')
	for speaker in speaker_parts:
		print('processing speaker ' + speaker)
		speaker_output_path = os.path.join(output_path, speaker)
		os.makedirs(speaker_output_path, exist_ok=True)
		metadata = ''
		for part in speaker_parts[speaker]:
			clip_fname = episode_title[3:6] + '_' + str(part.start_in_seconds) + '_' + str(part.end_in_seconds) + '_' + hex(abs(hash(part.text)))[2:] + '.wav'
			if not metadata_only:
				print('processing clip')
				clip = sound[part.start_in_seconds*1000:part.end_in_seconds*1000]
				wavs_path = os.path.join(speaker_output_path, 'wavs')
				clip_path = os.path.join(wavs_path, clip_fname)
				os.makedirs(wavs_path, exist_ok=True)
				clip.export(clip_path, format = 'wav')
			metadata += clip_fname[:-4] + '|' + part.text + '|' + part.text + '\n'
		fmeta_lock.acquire() if fmeta_lock is not None else None
		fmeta = open(os.path.join(speaker_output_path, 'metadata.csv'), 'a+')
		fmeta.write(metadata)
		fmeta.close()
		fmeta_lock.release() if fmeta_lock is not None else None
		print('done')
	if ignored_speakers:
		print(episode_title + ': ignored speakers ' + str(ignored_speakers))

def preprocess_rss(uri, cachedir=CACHEDIR):
	from xml.dom import minidom
	from urllib import request
	import os
	# fetch feed first and remove all but vtt transcripts
	rss = cache_fetch(uri, fname='rss.xml', cachedir='cache')
	xmldoc = minidom.parse(rss)
	itemlist = xmldoc.getElementsByTagName('podcast:transcript')
	for item in itemlist:
		if item.getAttribute('type') != 'text/vtt':
			p = item.parentNode
			p.removeChild(item)
	filepath = os.path.join(cachedir, 'rss_mod.xml')
	file_handle = open(filepath, 'w+')
	xmldoc.writexml(file_handle)
	file_handle.close()
	return filepath

def cache_fetch(uri, cachedir=None, fname=None, ext=''):
	from urllib.parse import urlparse
	from urllib import request
	import os
	fname = fname if fname is not None else os.path.basename(urlparse(uri).path)
	local_path = os.path.join(cachedir, fname + ext)
	if not os.path.exists(local_path):
		print('downloading ' + uri)
		os.makedirs(cachedir, exist_ok=True)
		request.urlretrieve(uri, local_path)
	return local_path

def parse_rss(uri, num_episodes=None, episodes_dir='cache/episodes'):
	import feedparser
	import os
	feed = feedparser.parse(preprocess_rss(uri))
	entries = []
	num_episodes = len(feed.entries) if num_episodes is None else num_episodes
	for i in range(num_episodes):
		entry = feed.entries[i]
		if 'podcast_transcript' not in entry:
			print('ignore ' + entry['title'] + ': no transcript')
			continue
		audio = next((x for x in entry['links'] if x['rel'] == 'enclosure'), None)
		if audio is None:
			print('ignore ' + entry['title'] + ': no audio')
			continue
		audio = audio['href']
		transcr = entry['podcast_transcript']['url']
		# download episode and transcript
		audio = cache_fetch(audio, cachedir=episodes_dir)
		transcr = cache_fetch(transcr, cachedir=episodes_dir, ext='.vtt')
		entries += [{
			'title': entry['title'],
			'audio': audio,
			'transcript': transcr,
		}]
	return entries


def install_requirements():
	import subprocess
	import sys
	subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def main():
	install_requirements()
	output = 'output'
	num_episodes = 3
	metadata_only = False
	if not metadata_only:
		clean_dir(output)
	episodes = parse_rss('https://feeds.metaebene.me/lnp/m4a', num_episodes=num_episodes)
	threads = []
	for episode in episodes:
		import threading
		fmeta_lock = threading.Lock()
		print('spawning thread')
		thread = threading.Thread(
				name=episode['title'],
				target=split_and_export_track,
				args=(episode['title'], episode['audio'], episode['transcript']),
				kwargs={"output_path": output, "metadata_only": metadata_only, "fmeta_lock": fmeta_lock})
		thread.start()
		print('spawned')

if __name__ == '__main__':
	main()
