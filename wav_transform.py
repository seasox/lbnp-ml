from pathlib import Path

import os
import subprocess
import soundfile as sf
import pyloudnorm as pyln
import sys

def wav_transform(src, cachedir='cache/'):
    paths = Path(src).glob("**/*.wav")
    
    for filepath in paths:
        target_filepath=Path(str(filepath) + '.converted.wav')
        target_dir=os.path.dirname(target_filepath)
    
    
        print("WAVTRANS From: " + str(filepath))
        print("WAVTRANS To: " + str(target_filepath))
    
        # Stereo to Mono; upsample to 48000Hz
        subprocess.run(["sox", filepath, cachedir + "48k.wav", "remix", "-", "rate", "48000"])
        subprocess.run(["sox", cachedir + "48k.wav", "-c", "1", "-r", "48000", "-b", "16", "-e", "signed-integer", "-t", "raw", cachedir + "temp.raw"]) # convert wav to raw
        #subprocess.run([rnn, "temp.raw", "rnn.raw"]) # apply rnnoise
        subprocess.run(["sox", "-r", "48k", "-b", "16", "-e", "signed-integer", cachedir + "temp.raw", "-t", "wav", cachedir + "rnn.wav"]) # convert raw back to wav
    
        subprocess.run(["mkdir", "-p", str(target_dir)])
        subprocess.run(["sox", cachedir + "rnn.wav", str(target_filepath), "remix", "-", "highpass", "100", "lowpass", "7000", "rate", "22050"]) # apply high/low pass filter and change sr to 22050Hz
    
        data, rate = sf.read(target_filepath)
    
        # peak normalize audio to -1 dB
        peak_normalized_audio = pyln.normalize.peak(data, -1.0)
    
        # measure the loudness first
        meter = pyln.Meter(rate) # create BS.1770 meter
        loudness = meter.integrated_loudness(data)
    
        # loudness normalize audio to -25 dB LUFS
        loudness_normalized_audio = pyln.normalize.loudness(data, loudness, -25.0)
    
        sf.write(target_filepath, data=loudness_normalized_audio, samplerate=22050)

        os.remove(filepath)
        os.rename(target_filepath, filepath)
    
        print("")

if __name__ == '__main__':
	wav_transform(sys.argv[1])

