import random
import logging
from os import listdir,stat
from os.path import join
from subprocess import Popen
import os
import time
import psutil
import datetime
from tinytag import TinyTag

class Videos:
    """
    Play and manage videos
    """

    player = None
    
    def __init__(self,video_dir):
        self.video_dir = video_dir
        self.last_video_dir_mtime = 0
        self.get_videos()


    def get_video(self):
        """
        select a random video to play
        """

        # see if the contents of the video directory have changed since last scan
        statinfo = stat(self.video_dir)
        if statinfo.st_mtime != self.last_video_dir_mtime:
            logging.info("video directory changed. Rescanning")
            self.get_videos()
            self.last_video_dir_mtime = statinfo.st_mtime

        return random.choice(self.videos)


    def get_videos(self):
        """
        get info on all the videos in the video directory
        """
        self.videos=[]
        for f in listdir(self.video_dir):
            if not f.endswith(".mp4"):
                continue
            absolute_path = join(self.video_dir,f)

            # get the video file metadata
            tag = TinyTag.get(absolute_path)
            video={'filename':absolute_path,
                   'duration':tag.duration}
            self.videos.append(video)
        return self.videos

    
    def remove(self,video):
        """
        remove the video with the given filename
        """
        path = join(self.video_dir,video)
        try:
            os.remove(path)
        except FileNotFoundError:
            logging.error("File not found: "+path)


    def _terminate_process(self,pid):
        """
        terminate a process and all its children
        """
        p = psutil.Process(pid)
        children = p.children()
        for child in children:
            child.terminate()
        gone, alive = psutil.wait_procs(children,timeout=3)
        for child in alive:
            # process still lingering; forefully kill it
            logging("Child PID {} didn't terminate. Killing.".format(child.pid))
            child.kill()
        
        p.terminate()
        p.wait(timeout=3) # maybe this will address the zombie process problem?
        # do a wait and p.kill() if process sticks around?

            
    def _omxplayer_timestamp(self,s):
        # convert number of seconds to an omxplayer-style HH:MM:SS timestamp
        ts = datetime.timedelta(seconds=s)
        return str(ts)

    
    def play_video(self,mute=False,clip_duration=0):
        """
        select a random video and play it
        """

        play_clips = clip_duration > 0

        # get a random video to play
        video = self.get_video()
        video_file = video['filename']
        
        args = ['/usr/bin/omxplayer','-b','--no-osd']

        if mute:
            # not sure how reliable omxplayer -n -1 is, but not
            # sure of any better alternatives for muting
            args.extend(["-n","-1"])


        video_duration = int(video['duration'])

        # default: play entire video
        timestamp = self._omxplayer_timestamp(0)
        duration = video_duration
    
        if play_clips and video_duration > clip_duration:
            # pick a random section of the video to play
            start = random.randint(0,video_duration-clip_duration)
            duration = clip_duration
            timestamp = self._omxplayer_timestamp(start)
            args.extend(["--pos",timestamp])

        args.append(video_file)

        logging.info("playing {}@{}".format(video_file,timestamp))

        try:
            self.player = Popen(args)
        except Exception:
            logging.exception("process creation failed: ")
            logging.info(args)
            return None

        self.player_duration = duration
        self.player_start = time.time()

        return video

    
    def is_finished(self):
        """
        Check if video is done playing
        """
        now = time.time()
        finished = False
        if self.player is None:
            finished = True
        elif self.player.poll() is not None:
            # player process has finished
            finished = True
        elif now >= self.player_start + self.player_duration:
            # player still running, clip end time reached
            self._terminate_process(self.player.pid)
            finished = True

        if finished:
            # reset everything
            self.player = None
            self.player_start = 0
            self.player_duration = 0
        
        return finished
    
