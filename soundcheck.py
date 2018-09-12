from pybass import *

file_name = 'wastes.ogg'
BASS_Init(-1, 44100, 0, 0, 0)
handle = BASS_StreamCreateFile(False, file_name, 0, 0, BASS_SAMPLE_LOOP)
play_handle(handle, show_tags = False)
BASS_Free()