import os
import io
import cv2
import sys
import json
import enum
import time
import dill
import heapq
import shutil
import pickle
import base64
import openai
import random
import asyncio
import requests
import warnings
import jsonpickle
import collections
import numpy as np
import pandas as pd
import networkx as nx
import random as rand
from PIL import Image
from scipy import ndimage
from datetime import datetime
import matplotlib.image as img
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import matplotlib.patches as patches
from matplotlib.patches import Polygon
from dateutil.relativedelta import relativedelta
from playwright.async_api import async_playwright
from IPython.display import display, Image as IPImage
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

class AIMegaDungeon:
      
    def __init__(self, 
                 filename='Test', 
                 levelfile='levels.csv', 
                 keys='|', 
                 game='D&D 5E 2024', 
                 rel_year =  -670, 
                 rel_day = 180, 
                 bastion='Town of Halsford', 
                 dungeon='The Mines of Thorvaldin'):
        '''
      

        levels -> a dict of dungeon objects, each representing a level of the dungeon.

        level_info -> level information, key is z coordinate (0 for first level)

        self.doors -> door information, 
        
        keys = OPENAI API KEY|OPENROUTER API KEY
        '''
        self.filename = filename
        
       
            
        
        # Get the directory of the class
        self.current_dir = os.path.dirname(os.path.abspath(__file__)) 
        self.game = game
        self.G = nx.Graph()
        self.time = 0  #in seconds...
        self.rel_year = rel_year
        self.rel_day = rel_day
        self.timers = []
        self.bastion = bastion
        self.levels = {}
        self.quests = []
        self.current_room = None
        self.dungeon_name = dungeon
        self.levelsdf = pd.read_csv(self.file_path(levelfile), sep='\t')
        self.npcs = {}
        try:
            self.load(filename)
        except:
            print('New Dungeon...')
        self.OPENAI_API_KEY = keys.split('|')[0]
        self.OPENROUTER_API_KEY = keys.split('|')[1]
        with open(self.file_path('AppendixA.pickle'), 'rb') as file:   
            self.AppendixA = pickle.load(file)
        print('Dungeon {} Created'.format(filename))
            
        self.char_level_ave = 1
    
    def __getstate__(self):
        # Capture everything
        return self.__dict__.copy()
        
    def __setstate__(self, state):
        self.__dict__.update(state)
        # Manually restore the child's reference to this parent instance
        for lvl in self.levels.keys():
            self.levels[lvl].parent = self
        
    ## ADMIN FUNCTIONS
    def file_path(self, filename):
        return os.path.join(self.current_dir, '{}'.format(filename))
           
    def save(self, filename='QuickSave'):
        '''
        
        Save bookeeping functions and the dungeon
        '''
        sys.setrecursionlimit(50000)
        self.filename = filename
        #frozen = jsonpickle.encode(self, keys=True)
        with open(self.file_path(filename+'.aad'), 'wb') as file:
            temp = (self.OPENAI_API_KEY , self.OPENROUTER_API_KEY)
            del self.OPENAI_API_KEY   
            del self.OPENROUTER_API_KEY
            dill.dump(self, file, protocol=dill.HIGHEST_PROTOCOL)  
            self.OPENAI_API_KEY , self.OPENROUTER_API_KEY = temp
              
    def load(self, filename=None):
        '''
        Load bookeepiung functions
        '''
        sys.setrecursionlimit(50000)
        # If no filename is provided, fall back to the instance's default
        if filename is None:
            filename = self.filename
        with open(self.file_path(filename+'.aad'), 'rb') as file:
            loaded_dungeon= dill.load(file)
        self.__dict__.update(loaded_dungeon.__dict__)
        print('depickled and attributes updated...')

    ## STRICT TIMEKEEPING
    def date(self):
        return datetime.fromtimestamp(self.time) + relativedelta(years=self.rel_year, days=self.rel_day)
    
    def make_date(self, s):
        return datetime.fromtimestamp(s) + relativedelta(years=self.rel_year, days=self.rel_day)
    
    def future_date(self, days):
        return datetime.fromtimestamp(self.time) + relativedelta(years=self.rel_year, days=self.rel_day) + relativedelta(days=days)
    
    def get_day(self, date=None, output=''):
        if date == None:
            date = self.date()
            
        day = date.day              # e.g., 6
        month = date.month          # e.g., 3
        weekday = date.weekday()    # Monday is 0, Sunday is 6
        isoweekday = date.isoweekday() # Monday is 1, Sunday is 7
        
        if output=='day':
            return date.strftime("%A")
        elif output == 'daynum':
            ans = date.strftime("%d")
        elif output == 'month':
            ans = date.strftime("%B")
        else:
            ans = date.strftime("%A, %B %d.")
            
        #Allows fantasy renames to the calendar
        try:
            df = pd.read_csv(self.file_path('calendar.csv'))
            for i, row in df.iterrows():
                ans = ans.replace(row['real'],row['fantasy'])
        except:
            None
        return ans
        
    def timekeeping(self):
        ret_lst = []
        ret_lst.append('{} [{}]'.format(self.get_day(self.date()), self.date()))
        
        # timers...
        ret_lst.extend(['EXPIRED! {}'.format(timer[1]) for timer in self.timers if timer[0] <= self.time])
        [self.timers.remove(timer) for timer in self.timers if timer[0] < self.time]
        lst = [timer for timer in self.timers if timer[0] > self.time]
        lst = sorted(lst, key=lambda x:x[0])
        ret_lst.extend(['{} [Time Remaining {}s]'.format(timer[1], timer[0] - self.time) for timer in lst])
        
        # clear old quests
        lst = sorted(self.quests, key=lambda x:x[0])
        self.quests = [quest for quest in lst if quest[0] > self.time]
        for quest in [quest for quest in lst if quest[0] <= self.time]:
            if quest[-1] != '':
                room = quest[-2]
                room.furnishings.append('General: The corpse of {}, recently slain'.format(room.captive_name))
                room.quest = ''
            
        return ret_lst
              
    def add_timer(self, event, hours=0, s=0, days=0, mins=0, rnds=0, turns=0):
        hours = hours + 24*days
        mins = mins + 10*turns + 60*hours
        s = self.time + s + 60*mins + 6*rnds
        self.timers.append((s,event))

    def pass_time(self, hours=0, s=0, days=0, mins=0, rnds=0, turns=0):
        hours = hours + 24*days
        mins = mins + 10*turns + 60*hours
        self.time = self.time + s + 60*mins + 6*rnds
        return self.timekeeping()
        
    def extend_timer(self, event, hours=0, s=0, days=0, mins=0, rnds=0, turns=0):
        lst = [timer for timer in self.timers if event.lower() in timer[1].lower()]
        if len(lst) == 0:
            print('{} not found.'.format(event))
        elif len(lst) > 1:
            print('Which {}: {}'.format(event, ', '.join([timer[1] for timer in lst])))
        else:
            timer = lst[0]
            self.timers.remove(timer)
            hours = hours + 24*days
            mins = mins + 10*turns + 60*hours
            s = timer[0] + s + 60*mins + 6*rnds
            ntimer = (s, timer[1])
            self.timers.append(ntimer)
        self.timekeeping()
     
    ## Quests
    def get_quests(self):
        '''
        self.quests.append((s,quest_name,reward,rumor,prompt,room,captive_name))
        '''
         # clear old quests
        lst = sorted(self.quests, key=lambda x:x[0])
        self.quests = [quest for quest in lst if quest[0] > self.time]
        for quest in [quest for quest in lst if quest[0] <= self.time]:
            if quest[-1] != '':
                quest[-2].furnishings.append('General: The corpse of {}, recently slain'.format(captive_name))
            quest[-2].quest = ''
        
        return ['{} [{} gold]'.format(quest[1], quest[2]) for quest in self.quests]
    
    def make_quest(self):
        '''
        Creates a quest using Random Tables and AI

        '''
        try_again = True
        while try_again == True:
            # GOAL
            goals = ['Stop the dungeon’s monstrous inhabitants from raiding the surface world.',
                     'Foil a villain’s evil scheme.',
                     'Destroy a magical threat inside the dungeon.',
                     'Acquire treasure.',
                     'Find a particular item for a specific purpose.',
                     'Retrieve a stolen item hidden in the dungeon.',
                     'Acquire treasure.',
                     'Find a particular item for a specific purpose.',
                     'Retrieve a stolen item hidden in the dungeon.',
                     'Find information needed for a special purpose.',
                     'Rescue a captive.',
                     'Discover the fate of a previous adventuring party.',
                     'Find an NPC who disappeared in the area.',
                     'Slay a dragon or some other challenging monster.',
                     'Discover the nature and origin of a strange location or phenomenon.',
                     'Parley with a villain in the dungeon.']
            goal = random.sample(goals,1)[0]
            patrons = ['Retired adventurer',
                       'Local ruler',
                       'Military officer',
                       'Temple official',
                       'Sage',
                       'Respected elder',
                       'Desperate commoner',
                       'Embattled merchant']
            patron = random.sample(patrons,1)[0]
            levels = []
            for level in self.levelsdf['level']:
                levels.extend([row['level'] for i, row in self.levelsdf.iterrows() if abs(row['level']) <= abs(level) and abs(level) <= len(self.quests)])
            floor = random.sample(levels,1)[0]
            reward = [0, 50, 100, 150, 250, 500, 600, 750, 900, 1100, 1200, 1600, 2000, 2200, 2500][random.randint(1,3)+abs(floor)]
            monster = ''
            monster_notes = ''
            captive = ''
            captive_name = ''
            trick = ''
            if 'phenomenon' in goal:
                trick = 'phenomenon'
            if 'NPC' in goal or 'captive' in goal:
                patrons.extend(['Old friend',
                                'Former teacher',
                                'Parent or other family member',
                                'Skilled adventurer',
                                'Inexperienced adventurer',
                                'Enthusiastic commoner',
                                'Soldier',
                                'Priest',
                                'Sage',
                                'Revenge seeker'
                                'Raving lunatic'])
                captive = random.sample(patrons,1)[0]
                prompt = 'I need a name and brief description (gender, race) for a single {}. This is for {}.  Format should be Name (gnder, race, single detail)'.format(captive, self.game)
                captive_name = self.get_chat_response(prompt)
            if 'inhabitants' in goal or 'villain' in goal or 'captive' in goal:
                monster = random.sample(self.levelsdf[self.levelsdf['level'] == floor]['Monster (dominant inhabitant)'].values[0].split('|'),1)[0]
                if 'captive' in goal:
                    
                    monster_notes = ' [Who captured {}, a {} (of the {})]'.format(captive_name, captive, patron)
                if 'raiding' in goal:
                    monster_notes = ' [Who are plaining on raiding the {}]'.format(self.bastion)
            elif captive != '':
                goal = goal + ' [{}, a {} (of the {})]'.format(captive_name, captive, patron)
                
            elif 'magical threat' in goal or 'dragon' in goal:
                monster = random.sample(self.levelsdf[self.levelsdf['level'] == floor]['Monster (random creature)'].values[0].split('|'),1)[0]
            treasure = ''
            actual_treasure = ''
            if 'item' in goal or 'treasure' in goal:
                treasure = random.sample(['gem','art','Magic Item'],1)[0]
            # find the room...
            lst = [room for room in self.levels[floor].rooms if room.quest == '' and 
                                                                room.description == '' and 
                                                                'stair' not in room.purpose.lower() and 
                                                                'exit' not in room.purpose.lower() and
                                                                'Door trap' not in room.purpose]
            if monster != '':
                lst = [room for room in lst if monster.lower() in room.monster.lower()]
            if treasure != '':
                lst = [room for room in lst if treasure.lower() in room.treasure.lower()]
            if trick != '':
                lst = [room for room in lst if 'trick' in room.treasure.lower()]
            try:
                room = random.sample(lst,1)[0]
                room.captive_name = captive_name
                room.monster = room.monster + monster_notes
                if trick != '':
                    goal = goal + ' [{}]'.format(room.traps)
                if treasure != '':
                    tprompt = f"I need to specify the results of a SINGLE {treasure}s in {room.treasure}."
                    tprompt = tprompt + f"ONLY REPORT THE ITEM [if a weapon or armor piece, also determine the type of weapon or armor]"
                    tprompt = tprompt + f"Completley specify one {treasure} for quest development reasons, and just return the item and it's details"
                    if 'magic' in treasure.lower():
                        tprompt = tprompt + f"   Magical Items for thi purpose cannot be temporary, so no Potions or Scrolls please."
                    actual_treasure = self.get_chat_response(tprompt,role='Someone that is concise')
                    room.treasure = room.treasure + ' where one of the {}s is already known to be a {}'.format(treasure, actual_treasure)
            
                days_to_complete = random.randint(1+abs(floor),3*(1+abs(floor)**2))
                prompt = f"Write a quest hook, in the form of a rumor board listing, for an adventure where a {patron} from {self.bastion} offers {reward} gold "
                prompt = prompt + f"for someone to enter {self.dungeon_name} in order to {goal}"
                if room.monster != '':
                    prompt = prompt + f"\n    Creatures Involved: {room.monster}"
                if treasure != '':
                    prompt = prompt + f"\n    Item/Treasure: {actual_treasure}"
                prompt = prompt + f"\nProvide the details the quest giver would know, and any details below he could suspect"
                prompt = prompt + f"\nFor details suspected, make sure they are listed in a logical way"
                prompt = prompt + f"\nNote that this takes place in a dungeon, only include information the quest giver would know in a way that they would know it." 
                prompt = prompt + f"\n    Goal is on Floor: {floor} [{self.levels[floor].info['purpose']}], room: {room.purpose}"
                prompt = prompt + f"The deadline is {self.get_day(self.future_date(days_to_complete))}"
                prompt = prompt + '''
    The format should be as follows:

    TITLE
    REWARD

    DETAILS

    Where TITLE is a catchy title to grab an adventurer's attention, but must hold some detail as to the adventure (don't say lost heirloom, say Lost sword if the heirloom is a sword, etc.)
    the REWARD is the gold offered (sometimes with 'and all other items found' and the like
    especially when the quest is for an item), and details is where you have the quest giver's name and what little information they have to go on.  
    Remember that the quest giver may not have all the information I have given you, and thus it wouldn't be in the listing.  Do not include floor numbers.
    Note floors start at 0, and tend to go down in negative numbers (0 not lowest)
    
    MAKE SURE TITLE IS ON THE FIRST LINE
                '''
                try_again = False
            except ValueError:
                try_again=True
        rumor = self.get_chat_response(prompt, role='You are a talented fantasy author making a handout for a TTRPG')
        room.quest = rumor
        if 'NPC' in goal:
            room.monster = room.monster + '{} [a {} (of the {})]'.format(captive_name, captive, patron)
        quest_name = rumor.split('\n')[0]

        s = self.time + 24*3600*days_to_complete
        self.quests.append((s,quest_name,reward,rumor,prompt,room,captive_name))
        
    def get_quest(self, title, dm=False):
        lst = [quest for quest in self.quests if title.lower() in quest[1].lower()]
        if len(lst) == 1:
            print(lst[0][3])
            if dm == True:
                return lst[0]
        else:
            lst = [quest[1] for quest in lst]
            print('Which one? {}'.format(', '.join(lst)))
               
    def take_quest(self, title):
        lst = [quest for quest in self.quests if title.lower() in quest[1].lower()]
        if len(lst) == 1:
            self.timers.append((lst[0][0], lst[0][1]))
        else:
            lst = [quest[1] for quest in lst]
            print('Which one? {}'.format(', '.join(lst)))
    
    ## Dungeon Functions
    def make_dungeon(self, rooms=35, start=False, finish=False):
        """
        This tries to make the dungeon...
        - it adds rooms rooms to the dungeon
        - start adds a starting area to level 0
        - finish eliminates the extra free doors
        """
        
        if start: # must be done when you first build it...
            self.levels = {}
            self.corridors = []
            for i, row in self.levelsdf.iterrows():
                self.levels[row['level']] = Dungeon(info=row, parent=self)
            self.levels[0].starting_room()

        min_level = 0
        max_level = 0
        # then we build or expand by rooms...
        for i in range(rooms):
            print('{}%'.format(int(100*i/rooms)),'\r')
            has_rooms = 0
            max_rooms = 0
            wait = False
            for lvl, row in self.levelsdf.iterrows():
                check = len(self.levels[row['level']].rooms)
                if check > max_rooms:
                    max_rooms = check
                if check > 0:
                    has_rooms += 1
            for lvl, row in self.levelsdf.iterrows():
                check = len(self.levels[row['level']].rooms)
                if check < max_rooms:
                    wait = True
            for lvl, row in self.levelsdf.iterrows():    
                self.levels[row['level']].add_area()
                # add rooms to smaller and "new" levels
                tries = 0
                while len(self.levels[row['level']].rooms) < max_rooms + random.randint(-7,0) and len(self.levels[row['level']].rooms) != 0 and self.levels[row['level']].check_free_doors() >= 1 and tries <= 100:
                    self.levels[row['level']].add_area()
                    tries += 1     
                if len(self.levels[row['level']].rooms) > 0 and row['level'] > max_level:
                    max_level = row['level']
                elif len(self.levels[row['level']].rooms) > 0 and row['level'] < min_level:
                    min_level = row['level']
        if finish == True:
            #kill doors
            for lvl, row in self.levelsdf.iterrows():
                dungeon = self.levels[row['level']]
                [dungeon.remove_door(door) for door in dungeon.get_free_doors()]
        self.G = nx.Graph()
        self.graph_dungeon()
        return min_level, max_level

    def graph_dungeon(self, secrets=True, monsters=True, traps=True):
        '''
        Creates a NetworkX graph of the dungeon, where doors and rooms are nodes
        this allows calculation of quickest paths and allows the next door in quickest path
        to be found.
        '''
        secweight = 0
        monweight = 0
        trapweight = 0
        if secrets == False:
            secweight = 5
        if monsters == False:
            monweight = 5
        if traps == False:
            trapweight = 5
        # Add to graph
        self.G = nx.Graph()
        # We rebuild the graph each time in case doors are cut off
        for lvl, row in self.levelsdf.iterrows():
            # add to Graph...
            for room in self.levels[row['level']].rooms:
                rm_type = 'room'
                weight = 1
                if room.stairs != None:
                    self.G.add_edge(room, room.stairs, weight=1)
                    rm_type = 'stair'
                elif room.is_exit == True:
                    rm_type = 'exit'
                self.G.add_node(room
                            , type=rm_type
                            , label='{}'.format(' '.join(room.purpose.split(' ')[0])))
                if room.monster != '':  #room has monsters...
                    weight = weight + monweight
                for door in room.doors:
                    nweight = weight
                    if 'secret' in door.door_type.lower():  # hide secret doors that arn't needed...
                        nweight = nweight+secweight
                    if door.trapped == True:  # hide traps that arn't needed...
                        nweight = nweight+trapweight
                    self.G.add_edge(room, door, weight=nweight)
                    self.G.add_node(door, type='door',label=door.door_type.split(' ')[0].replace(',',''))
                    
    def get_dungeon_floorplans(self, show=True, levels=None):
        '''
        Creates floor graphs of the dungeon.  
        This isn't necessary, but can be fun to look at
        '''
        if levels == None:
            levels = [row['level'] for lvl, row in self.levelsdf.iterrows()]
        if type(levels)==int:
            levels = [levels]
        
        for lvl, row in self.levelsdf.iterrows():
            if len(self.levels[row['level']].rooms) > 0 and row['level'] in levels:
                print('Level', row['level'], 'rooms', len(self.levels[row['level']].rooms))
                print('free doors', self.levels[row['level']].check_free_doors())
                print('Exits', sum([room.is_exit for room in self.levels[row['level']].rooms]))
                print('Stairs', len([room for room in self.levels[row['level']].rooms if 'stairwell' in room.purpose.lower()]))
                self.levels[row['level']].draw_dungeon(show)

    def check_dungeon(self):
        '''
        This outputs levels that have rooms, as well as
        - number of rooms
        - free doors
        - Exits
        - Stairs
        Good for determining if the dungeon is the correct size without
        knowing the layout
        '''
        for lvl, row in self.levelsdf.iterrows():
            if len(self.levels[row['level']].rooms) > 0:
                print('Level', row['level'], 'rooms', len(self.levels[row['level']].rooms))
                print('free doors', self.levels[row['level']].check_free_doors())
                print('Exits', sum([room.is_exit for room in self.levels[row['level']].rooms]))
                print('Stairs', len([room for room in self.levels[row['level']].rooms if 'stairwell' in room.purpose.lower()]))
    
    def remove_room(self, room):
        # kill the borders
        if room.stairs:
            room.stairs.stairs = None
            room.parent.remove_room(room.stairs)
        for door in room.doors:
            for border in door.borders:
                if border.position.point() in [block.position.point() for block in room.blocks]:
                    door.borders.remove(border)
                    # corridors
                    for corridor in room.parent.corridors:
                        if corridor.start_border == border or corridor.stop_border == border:
                            room.parent.corridors.remove(corridor)
            # kill the doors..
            door.rooms.remove(room)
        # remove the room
        room.parent.rooms.remove(room)
        del room
    
    def check_traps(self):
        '''
        Makes sure that Door Trap rooms have traps attached to the door and the room.
        '''
        for level in self.levels:
            for room in self.levels[level].rooms:
                if room.purpose == 'Door Trap' and room.traps == '':
                    for door in room.doors:
                        door.trapped = True
                        door.traps = 'Trap({}): {} [Trigger: {}]\n'.format(room.parent.parent.roll_table(room.parent.parent.AppendixA['Random Traps']['Trap Damage Severity'])
                                                             , room.parent.parent.roll_table(room.parent.parent.AppendixA['Random Traps']['Trap Effects'])
                                                             , random.choice(['Touched (doorknob)', 'Opened (door)', 'Opened (door)']))
                        for rm in door.rooms:
                            rm.traps = door.traps
        # fix trap triggers
        for level in self.levels.values():
            for room in level.rooms:
                if room.traps != '':
                    if room.traps[:5] == 'Trick':
                        new_feature = room.traps.split(':')[0].replace('Trick ','')
                        room.furnishings.append('General Furnishings and Appointments: {}'.format(new_feature))
                    else:
                        trigger_bit = random.choice([a for a in room.furnishings if 'Furnishings' in a])
                        trigger_bit = trigger_bit.split(':')[1]
                        trigger_bit = random.choice([a for a in room.furnishings if 'Furnishings' in a])
                        trigger_bit = trigger_bit.split(': ')[1]
                        room.traps.replace('Touched (doorknob, statue)','Touched ({})'.format(trigger_bit))
                        room.traps.replace('Looked at (mural, arcane symbol)','Looked at ({})'.format(trigger_bit))
                        room.traps.replace('Moved (cart, stone block)','Moved ({})'.format(trigger_bit))
         
    def enter_dungeon(self, exit_level=0, exit_room_id=None):
        '''
        Allows a known level/room id to be used to set current room to that room so the room doesn't need to be saved.
        '''
        if exit_room_id == None:
            self.current_room = self.levels[0].rooms[0]
        else:
            room = self.levels[exit_level].rooms[exit_room_id]
            mydoor = room.doors[0]
            for rm in room.parent.rooms:
                for door in rm.doors:
                    if door == mydoor:
                        if rm != room:
                            self.current_room = rm
        return self.current_room
        
    ## D&D TABLES
    def roll_table(self, df):
        droll = random.randint(1,max(df['Roll']))
        return df[df['Roll']==droll]['Result'].values[0]
        
    def get_treasure(self, CR, hoard=False):
        '''
        '''
        treasure = 'No Extra Treasure'
        while treasure == 'No Extra Treasure':
            d100 = random.randint(1,100)
            rCR = 'CR 17+'
            if CR <= 4:
                rCR = 'CR 0-4'
            elif CR >= 5 and CR <= 10:
                rCR = 'CR 5-10'
            elif CR >=11 and CR <= 16:
                rCR = 'CR 11-16'
            
            if hoard:
                df = pd.read_csv(self.file_path('hoard treasure.csv'))
                rCR = rCR + ' Hoard'
                if d100 <= 6:
                    row = 0
                elif d100 >= 7 and d100 <= 16:
                    row = 1
                elif d100 >= 17 and d100 <= 26:
                    row = 2
                elif d100 >= 27 and d100 <= 36:
                    row = 3
                elif d100 >= 37 and d100 <= 44:
                    row = 4
                elif d100 >= 45 and d100 <= 52:
                    row = 5
                elif d100 >= 53 and d100 <= 60:
                    row = 6
                elif d100 >= 61 and d100 <= 65:
                    row = 7
                elif d100 >= 66 and d100 <= 70:
                    row = 8
                elif d100 >= 71 and d100 <= 100:
                    row = 9
            else:
                df = pd.read_csv(self.file_path('individual treasure.csv'))
                if d100 <= 30:
                    row = 0
                elif d100 >= 31 and d100 <= 60:
                    row = 1
                elif d100 >= 61 and d100 <= 70:
                    row = 2
                elif d100 >= 71 and d100 <= 95:
                    row = 3
                elif d100 >= 96 and d100 <= 100:
                    row = 4
                    
            treasure = df[rCR].values[row]
            tlist = treasure.split(' ')
            ntlist = []
            for item in tlist: 
                if len(item) >= 2:
                    if item[1] == 'd':
                        temp = ''
                        lst = item.split('x')
                        n = int(lst[0].split('d')[0])
                        d = int(lst[0].split('d')[1])
                        temp = random.randint(n,n*d)
                        if len(lst)==2:
                            temp = temp*int(lst[1])
                        item = '{}'.format(temp)
                ntlist.append(item)
            treasure = ' '.join(ntlist)
        return treasure
 
    ## D&D FUNCTIONS
    def make_description(self, room):
        if room.description == '':
            if room.is_exit == True:
                room.description = 'This is an exit'
                return room.description
            else:
                room.color = 'green'
            CR = random.randint(1,3)+(2*abs(room.parent.info['level']))
            room_desc_basic = 'Purpose: {}'.format(room.purpose)
            room_desc_basic = room_desc_basic + '\n    State: {}'.format(room.state)
            doors = []
            for door in [door for door in room.doors if 'Secret' not in door.door_type]:
                for border in door.borders:
                    if border.position.point() in [block.position.point() for block in room.blocks]:
                        location = 'On the {} wall at {}'.format(direction_to_compass(border.direction),border.position.point())
                if 'Portcullis' not in door.door_type:
                    doors.append('   - {} Door [{}]'.format(door.door_type, location))
                else:
                    doors.append('{} [{}]'.format(door.door_type, location))
            if len(doors) >= 1:
                room_desc_basic = room_desc_basic + '\nDoors: \n{}'.format('\n'.join(doors))
            if room.monster != '':   # AI CALL
                if '[Rolled]' not in room.monster:
                    # add dungeon description
                    df = self.levelsdf[self.levelsdf['level']==room.parent.level]
                    
                    # reaction roll
                    
                    
                    prompt = 'Write a {} Encounter: Create a Medium CR {} encounter based around {}\n'.format(self.game, CR, room.monster)
                    prompt = prompt + '    - This encounter takes place on a level of thedungeon known as {} which is described as: {}'.format(df['name'].values[0],df['description'].values[0])
                    prompt = prompt + '    - Be sure to include a basic outline of combat strategy, as if you were the author of "The Monsters Know What They Are Doing", for the first 3 rounds of combat, including surrender conditions/motivations\n'
                    prompt = prompt + '    - Inclue any note on roleplay for the creatures.\n'
                    prompt = prompt + "    - Include the numbers of creatures, and adjust fro 4-6 characters"
                    prompt = prompt + "    - The monsters reaction to the players entering is: {}".format(monster_reaction())
                    prompt = prompt + '''    - Add an Esculation Clock appropriate to the room and encounter 
                    [Esculation Clocks track hazards (volcano eruptions, crumbling floors), NPC actions (guards arriving), or environmental changes (tide changes, magic fading)
                    The Escalation Clock Pattern
                        Duration: Set a countdown of 1d4+1 rounds (literally write 1d4+1...)
                        The Telegraph (The "Tell"): Describe a sensory warning that intensifies each round (e.g., a sound, a visual crack, a rising temperature).
                        The Payload (The "Snap"): Define a significant mechanical shift that occurs when the clock hits zero. It must either damage the players, block an path, or add new threats. It should change the "win condition" of the room.]\n
                        Payload should not add architecture.
                    '''
                    prompt = prompt + 'Use the minimum words needed to convey the info above for eas of use at the table.'
                    prompt = prompt + '\n\nInclude the statblocks/descriptions and lookup information (book, pg number) for each monster\n\n'
                    prompt = prompt + '\n\nRoom Description: {} [{}]'.format(room.purpose, room.state)
                    prompt = prompt + '    - room is {} square feet'.format(5*len(room.blocks))
                    prompt = prompt + '\n    Doors: \n{}'.format('        \n'.join(doors))
                    if room.traps != '' or room.hazards != '':
                        prompt = prompt + '\n    Traps & Hazards: {}'.format('; '.join([room.traps,room.hazards]))
                    prompt = prompt + '\n{}'.format('\n     '.join(room.furnishings))
                    encounter = self.get_chat_response(prompt, role='You are a talented Quest Writer for {}'.format(self.game))
                    room.monster = '[Rolled]' + room.monster +'\n\n' + encounter
                    room_desc_basic = room_desc_basic + '\n\nEncounter: ' + room.monster +'\n'
                else:
                    room_desc_basic = room_desc_basic + room.monster
            if room.treasure != '':  # Potential AI Call
                if ('art' in room.treasure or 'Table' in room.treasure or 'gems' in room.treasure) and '[Rolled]' not in room.treasure :
                    prompt = 'Roll on the appropriate d&d 5e 2024 tables and write details (gem types for gems, art description for art, etc.) for the following treasure: {}'.format(room.treasure)
                    treasure_rolls = self.get_chat_response(prompt, role='You are a talented Quest Writer for D&D 5e 2024')
                    room.treasure = '[Rolled] ' + room.treasure + '\n\n' + treasure_rolls
                    room_desc_basic = room_desc_basic + '\nTreasure: ' + room.treasure
                else: 
                    room_desc_basic = room_desc_basic + '\nTreasure: ' + room.treasure
            if room.traps != '':
                room_desc_basic = room_desc_basic + '\nTRAP: ' + room.traps
            if room.hazards != '':
                room_desc_basic = room_desc_basic + '\nHazard: {}'.format(room.hazards)
            for furnishing in room.furnishings:
                room_desc_basic = room_desc_basic + '\n{}'.format(furnishing)
            room_desc_basic = room_desc_basic + f"\nFloors: {room.parent.info['floors']}"
            room_desc_basic = room_desc_basic + f"\nCeiling [{room.ceiling_height}]: {room.parent.info['ceilings']}"
            
            room_desc_basic = room_desc_basic + f"\nWall: {room.parent.info['walls']}"
            room.description = room_desc_basic

            # Quest Completion
            if room.quest !='':
                room.old_description = room.description
                prompt = '''Incorporate the following quest into the description below.  This room is where the objective of this quest is to be found.
                -include any information that is left unkown, such as information, items, etc.
                -if an item is needed but not in the furnishings, describe how it is hidden.
                -Leave the description as close to intact as possible but inlcude the necessary information (edit, don't reformat/rewrite)
                -the quest is written down elsewhere, it does not need to be included in the description.
                
                Quest: {}
                
                Description: {}
                
                Do not extend the quest into any other rooms.  Everything involved is in thiis room
                Keep all parts of the description!  Just edit the description so the quest is taken into account.'''.format(room.quest, room.description)
                room.description = self.get_chat_response(prompt, role='You are an editor for a {} book'.format(self.game)) 
    
    def random_encounter(self, room, party_is='Exploring'):
        '''
        Rolls a random encounter...
        2d6 1 = shift level +1, roll again
            3-4 = Monster (random creature)
            5-6 = Monster (pet or allied creature)
            7 = Monster (dominant inhabitant)
            8-9 = Monster (pet or allied creature)
            10-11 = Monster (random creature)
            12 = shift level -1, roll again
        '''
        level = room.parent.info['level']
        encounter = ''
        while encounter == '':
            CR = random.randint(1,3)+abs(level)
            monster = ''
            n2d6 = random.randint(1,6)+random.randint(1,6)
            if n2d6 == 1:
                if sum(self.levelsdf['level']==level+1) == 1:
                    level = level +1
            elif (n2d6 >= 3 and n2d6 <= 4) or (n2d6 >= 10 and n2d6 <= 11):
                lst  = self.levelsdf[self.levelsdf['level']==level]['Monster (random creature)'].values[0].split('|')
                monster = lst[random.randint(0,len(lst)-1)]
                monster = '{} [Monster Motivation: {}]'.format(monster, self.roll_table(self.AppendixA['Monster Motivation']))
            elif (n2d6 >=5 and n2d6 <= 6) or (n2d6 >= 8 and n2d6 <= 9):
                lst  = self.levelsdf[self.levelsdf['level']==level]['Monster (pet or allied creature)'].values[0].split('|')
                monster = lst[random.randint(0,len(lst)-1)]
                monster = '{} [Monster Motivation: {}]'.format(monster, self.roll_table(self.AppendixA['Monster Motivation']))        
            elif (n2d6 == 7):
                lst  = self.levelsdf[self.levelsdf['level']==level]['Monster (dominant inhabitant)'].values[0].split('|')
                monster = lst[random.randint(0,len(lst)-1)]
                monster = '{} [Monster Motivation: {}]'.format(monster, self.roll_table(self.AppendixA['Monster Motivation']))
            elif (n2d6 == 12):
                if sum(self.levelsdf['level']==level-1) == 1:
                    level = level -1
            if monster != '':
                # get some info...
                df = self.levelsdf[self.levelsdf['level']==room.parent.level]
                
                prompt = 'The party is currently {} in a room described as: {}.  The room is on a level of the dungeon known as {} which is described as {}\n'.format(party_is, room.purpose, df['name'].values[0], df['description'].values[0])
                prompt = prompt + '\n\nWrite a {} Random Encounter: Create a Medium CR {} encounter based around {} entering the area\n\n'.format(self.game, CR,monster)
                prompt = prompt + '    - Be sure to include a basic outline of combat strategy, as if you were the author of "The Monsters Know What They Are Doing", for the first 3 rounds of combat, including surrender conditions/motivations\n'
                prompt = prompt + '    - Inclue any note on roleplay for the creatures.\n'
                prompt = prompt + "    - The monsters reaction to encountering the players is: {}".format(monster_reaction(-1))
                propmt = prompt + "Use as few wrods as possible to convey this information"
                prompt = prompt + '\n\nInclude the statblocks/descriptions and lookup information (book, pg number) for each monster\n\n'
                if room.description == '':
                    doors = []
                    for door in [door for door in room.doors if 'Secret' not in door.door_type]:
                        for border in door.borders:
                            if border.position.point() in [block.position.point() for block in room.blocks]:
                                location = 'On the {} wall at {}'.format(direction_to_compass(border.direction),border.position.point())
                        if 'Portcullis' not in door.door_type:
                            doors.append('   - {} Door [{}]'.format(door.door_type, location))
                        else:
                            doors.append('{} [{}]'.format(door.door_type, location))
                    prompt = prompt + '\n\nRoom Description: {} [{}]'.format(room.purpose, room.state)
                    prompt = prompt + '    - room is {} square feet'.format(5*len(room.blocks))
                    prompt = prompt + '\n    Doors: \n{}'.format('        \n'.join(doors))
                    if room.traps != '' or room.hazards != '':
                        prompt = prompt + '\n    Traps & Hazards: {}'.format('; '.join([room.traps,room.hazards]))
                    prompt = prompt + '\n{}'.format('\n     '.join(room.furnishings))
                else:
                    prompt = prompt + '\n\n(Note as the {} arrive, we are still running: {}, this is adding to that encounter)'.format(monster, room.description)
                encounter = self.get_chat_response(prompt, role='You are a talented Quest Writer for {}'.format(self.game))
                room.monster = '[Rolled] ' + ', '.join([a for a in [room.monster,monster] if a != '']) +'\n\n' + encounter
        return encounter 
  
    def track(self, target):
        '''
        If you succeed at a tracking check, this lets you know if there are tracks here
        and where they lead.
        '''
        self.graph_dungeon()
        lst = []
        for i in self.levels.keys():
            level = self.levels[i]
            lst.extend([room for room in level.rooms if target.lower() in room.monster.lower() or 
                                                        target.lower() in room.description or 
                                                        target.lower() in room.quest.lower()])
        if len(lst) > 1:
            check = [len(nx.shortest_path(self.G, source=self.current_room, target=room)) for room in lst]
            room = lst[check.index(min(check))]
        else:
            room = lst[0]
        # what entrance did they take?
        lst = []
        for i in self.levels.keys():
            level = self.levels[i]
            lst.extend([room for room in level.rooms if room.is_exit])
        check = [len(nx.shortest_path(self.G, source=room, target=eroom)) for eroom in lst]
        entrance = lst[check.index(min(check))]
        path = nx.shortest_path(self.G, source=entrance, target=room)
        if self.current_room in path:
            door = path[path.index(self.current_room)+1]
            if type(door) == Door:
                doortype = door.door_type.split(' ')[0].replace(',','')
                if 'portcullis' not in doortype:
                    doortype = '{} door'.format(doortype) 
                compass = direction_to_compass(door.borders[door.rooms.index(self.current_room)].direction)
                if 'secret' not in door.door_type.lower():
                    print(f"The tracks lead to the {doortype} to the {compass}")
                else:
                    print(f"The tracks lead into the {compass} wall")
            else:
                print(f"The tracks lead into the {self.current_room.purpose}")
        else:
            print(f"You don't see any tracks or footprints here")
    
    def explore(self,room=None,exit_id=None, exit_level=None):
        # first, we need the room we're in...
        if room == None:
            if exit_id == None:
                self.current_room = self.levels[0].rooms[0]
                room = self.current_room
            else:
                if exit_level == None:
                    exit_level = 0
                rooms = [room for room in self.levels[exit_level].rooms if room.room_id == exit_id]
                try:
                    room = rooms[0]
                except:
                    room = self.levels[0].rooms[0]
                self.current_room = room
        
        # lets do this...
        if room != None and room.is_exit == False:
            if room.description == '':
                self.make_description(room)
        output_image_path = self.file_path("Rooms/{} Level {} Room {}.png".format(self.filename,
                                                                                      room.parent.info['level'],
                                                                                      room.room_id))
        if len(room.blocks) >= 2:
            try:
                display(IPImage(filename=output_image_path))
            except:
                self.draw_room(room)
                self.render_room(room, show=True)

        lst = []
        dct = {}
        for door in room.doors:
            direction = direction_to_compass(get_door_border(room, door).direction)
            name = door.door_type.split(' ')[0].replace(',','')
            key = '{}-{}'.format(direction,name)
            if 'secret' not in key.lower():
                lst.append(key)
            dct[key] = door
        room.door_dct = dct
        if room.is_exit == True:
            lst.append('This is an exit, exit_id = Level = {}; Room-ID = {}'.format(room.parent.info['level'],room.room_id))
        return room, lst

    def open_door(self, door_key, unlocked=False):
        if door_key not in self.current_room.door_dct:
            return 'You need to specify a real door'
        else:
            door = self.current_room.door_dct[door_key]
            if 'locked' in door.door_type or 'barred' in door.door_type:
                if unlocked==True:
                    door.door_type = door.door_type.split(',')[0]
            reply = door.door_type
            if 'portcullis' not in reply:
                reply = reply + " door"
            if door.trapped == True and ',' not in door.door_type:
                reply = reply + '\n\n{}'.format(door.traps)
            if 'locked' not in door.door_type and 'barred' not in door.door_type:
                new_room = [room for room in door.rooms if room != self.current_room]
                self.current_room = new_room[0]
                reply = reply + '\n    ...opened'
        return reply
         
    def get_npc(self, 
               name, 
               vitals=None, 
               appearance=None, 
               abilities=None,
               talent=None,
               mannerisms=None,
               personality=None,
               notes=None):
        '''
        '''
        try:
            print(self.npcs[name.lower()])
        except:
            query = '''
            Write a 1-3 paragraph write up for an NPC, including motivations, combat startegies, and roleplaying notes.
            
            Chose an appropriate statblock from the monster manual, and make sure the write up makes sesne given the statblock.
            The statblock's species should match that of the NPC, or be a generic humanoid statblock.
            What we know about the NPC:
            '''.format(name)

            if vitals == None:
                if '(' in name:
                    lst = name.split(' (')
                    name = lst[0]
                    vitals = lst[1].replace(')','')
                else:
                    vitals = 'human'
            query = query + '\n\nName: {}'.format(name)
            query = query + '\nVitals: {}'.format(vitals)
        
            # appearance
            if appearance == None:
                choice = ['Distinctive jewelry: earrings, necklace, circlet, bracelets',
                          'Piercings', 'Flamboyant or outlandish clothes',
                          'Formal, clean clothes', 'Ragged, dirty clothes',
                          'Pronounced scar', 'Missing teeth', 'Missing fingers',
                          'Unusual eye color (or two different colors)', 'Tattoos',
                          'Birthmark', 'Unusual skin color', 'Bald',
                          'Braided beard or hair', 'Unusual hair color',
                          'Nervous eye twitch', 'Distinctive nose',
                          'Distinctive posture (crooked or rigid)',
                          'Exceptionally beautiful', 'Exceptionally ugly']
                appearance = random.sample(choice,1)[0]
                query = query + '\nAppearance: {}'.format(appearance)
        
            #abilities
            if abilities == None:
                high = ['Strength — powerful', 'Strength — brawny', 'Strength — strong as an ox',
                        'Dexterity — lithe', 'Dexterity — agile', 'Dexterity — graceful',
                        'Constitution — hardy','Constitution — hale', 'Constitution — healthy',
                        'Intelligence — studious', 'Intelligence — learned', 'Intelligence — inquisitive',
                        'Wisdom — perceptive', 'Wisdom — spiritual', 'Wisdom — insightful',
                        'Charisma — persuasive', 'Charisma — forceful', 'Charisma — born leader']
                abilities = 'High: {} '.format(random.sample(high,1)[0])
                low = ['Strength — feeble', 'Strength — scrawny',
                       'Dexterity — clumsy', 'Dexterity — fumbling',
                       'Constitution — sickly', 'Constitution — pale',
                       'Intelligence — incurious','Intelligence — slow',
                       'Wisdom — oblivious', 'Wisdom — absentminded',
                       'Charisma — dull', 'Charisma — boring']
                abilities = '{}, Low: {} '.format(abilities, random.sample(low,1)[0])
            query = query + '\nAbilities: {}'.format(abilities)
                
            #talent
            if talent == None:
                choice = ['Plays a musical instrument', 'Speaks several languages fluently',
                          'Unbelievably lucky', 'Perfect memory', 'Great with animals',
                          'Great with children', 'Great at solving puzzles', 'Great at one game',
                          'Great at impersonations', 'Draws beautifully', 'Paints beautifully',
                          'Sings beautifully', 'Drinks everyone under the table',
                          'Expert carpenter', 'Expert cook', 'Expert dart thrower and rock skipper',
                          'Expert juggler', 'skilled actor and master of disguise',
                          'Skilled dancer', 'Knows thieves’ cant']
                talent = random.sample(choice,1)[0]
            query = query + '\nTalent: {}'.format(talent)
        
            #mannerisms
            if mannerisms == None:
                choice = ['Prone to singing, whistling, or humming quietly', 
                          'Speaks in rhyme or some other peculiar way',
                          'Particularly low or high voice','Speaks in an unusually formal manner',
                          'Enunciates overly clearly', 'Speaks loudly', 'Whispers',
                          'Uses flowery speech or long words', 'Frequently uses the wrong word',
                          'Uses colorful oaths and exclamations','Makes constant jokes or puns',
                          'Prone to predictions of doom',  'Fidgets', 'Squints',
                          'Stares into the distance', 'Chews something', 'Paces',
                          'Taps fingers', 'Bites fingernails', 'Twirls hair or tugs beard']
                mannerisms = random.sample(choice,1)[0]
            query = query + '\nMannerisms: {}'.format(mannerisms)
        
            #personality
            if personality == None:
                choice = ['	Argumentative', 'Arrogant', 'Blustering', 'Rude', 'Curious', 'Friendly',
                          'Honest', 'Hot tempered', 'Irritable', 'Ponderous', 'Quiet', 'Suspicious']
                personality = random.sample(choice,1)[0]
            query = query + '\nPersonality: {}'.format(personality)    
        
            # notes
            if notes == None:
                choice = ['Beauty','Domination','Charity','Greed','Greater good','Might','Life',
                          'Pain','Respect','Retribution','Self-sacrifice','Slaughter','Community',
                          'Change','Fairness','Creativity','Honor','Freedom','Logic','Independence',
                          'Responsibility','No limits','Tradition','Whimsy','Balance','Aspiration',
                          'Knowledge','Discovery','Live and let live','Glory','Moderation','Nation',
                          'Neutrality','Redemption','People','Self-knowledge']
                notes = ' Ideal: {}'.format(random.sample(choice,1)[0])
                choice = ['Dedicated to fulfilling a personal life goal',
                          'Protective of close family members',
                          'Protective of colleagues or compatriots',
                          'Loyal to a benefactor, patron, or employer',
                          'Captivated by a romantic interest', 'Drawn to a special place',
                          'Protective of a sentimental keepsake',
                          'Protective of a valuable possession',
                          'Out for revenge']
                notes = '{} \n      Bond: {}'.format(notes, random.sample(choice,1)[0])
                choice = ['Forbidden love or susceptibility to romance',
                          'Enjoys decadent pleasures', 'Arrogance',
                          'Envies another creature’s possessions or station',
                          'Overpowering greed', 'Prone to rage',
                          'Has a powerful enemy','Prone to sudden suspicion',
                          'Shameful or scandalous history', 'Secret crime or misdeed',
                          'Possession of forbidden lore', 'Foolhardy bravery']
                notes = '{} \n      Flaw/Secret: {}'.format(notes, random.sample(choice,1)[0])
            query = query + '\nNotes: {}'.format(notes) 
        
            self.npcs[name.lower()] = self.get_chat_response(query, role="You are a TTRPG writer tasked to write up NPCs")
        return self.npcs[name.lower()]
    
    ## AI CALLS & TOOLS
    def get_chat_response(self, prompt, role="You are a helpful assistant.", model="google/gemini-2.5-flash"):
        print(model)
        prompt = prompt + '''
        
        Constraint: Do not acknowledge this request. Do not provide introductions, conclusions, or multiple options unless 
        specifically asked. Provide only the raw text of the quest board listing. Start your response immediately with the content.'''
        
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.OPENROUTER_API_KEY, 
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ],
            extra_headers={
                "HTTP-Referer": "https://github.com",
                "X-Title": "AI Mega Dungeon",
            }
        )
        return response.choices[0].message.content
         
    def draw_room(self, room, show=True):
        '''
        Creates a mask and base image for AI to draw the room from
        '''
        MY_DPI = 70        
        inner_radius = 0.25  # in case of stairs
        Diagonals = make_diagonals(room)
        fakeroom = make_fakeroom(room)
        borders = list(room.geometry_borders())
        wallborders = list(fakeroom.geometry_borders())
        
        # 1. FIX DIMENSIONS: Use 100 DPI for cleaner math, no padding here 
        # because the 'fakeroom' wallborders already define the outer boundary.
        figsize, (xmin, xmax), (ymin, ymax) = get_figsize_from_wallborders(wallborders, dpi=MY_DPI, pixels_per_unit=70, padding_units=1)
        
        
        fig = plt.figure(figsize=figsize, dpi=100)
        # 2. Add an axes that fills the literal 100% of the figure area
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect('equal')
        ax.axis('off')

        fig.set_facecolor('black')

        # --- DRAW MASK CONTENT ---
        # Mask the area white...
        ax.fill(*zip(*make_contour(wallborders)), '#ffffff', alpha=1, zorder=1)
        
        # Use EXACTLY these arguments to prevent Matplotlib from resizing
        save_kwargs = {
                'dpi': MY_DPI,
                'bbox_inches': None,
                'pad_inches': 0,
                'transparent': False
            }
       
        inner_wall_border_line = []
        if 'stairwell' in room.purpose.lower() and 'down' in room.purpose.lower():
            nborders = list(room.door_geometry_borders())
            ax.fill(*zip(*make_contour(nborders)), '#ffffff', zorder=2)
            for border in nborders:
                inner_wall_border_line.append(ax.plot(*zip(*border), color='k', linewidth=2, alpha=1, zorder=3))
        else:
            for border in borders:
                inner_wall_border_line.append(ax.plot(*zip(*border), color='k', linewidth=2, alpha=1, zorder=3))
        
        for border in wallborders:
             inner_wall_border_line.append(ax.plot(*zip(*border), color='k', linewidth=25, alpha=1.0, zorder=4))

        for coords in Diagonals:
            x, y = zip(*coords)
            inner_wall_border_line.append(ax.plot(x, y, color='k', linewidth=2, alpha=1.0, zorder=3))

         # add gridlines
        for border in room.grid_borders():
            plt.plot(*zip(*border), color='k', linewidth=1, alpha=0.5)

        # blue lines for doors
        for i, door in enumerate(room.doors):
            ddx, ddy = 0, 0 
            if 'Portcullis' in door.door_type:
                ddx, ddy = .2, .2
            for i, dborder in enumerate(door.borders):
                if dborder.position.point() in [block.position.point() for block in room.blocks]:
                    border = door.borders[i]
            x, y = border.position.point()
            xlst, ylst = [], []
            x_val, y_val = x, y
            # lower corner, other lower corner, upper 1, upper 2, lower 1 again
            frames = [0.25,0.75,.95,.05,0.25]
            if border.direction == DIRECTION.LEFT: 
                ylst = [y+frames[0]-ddy,y+frames[1]+ddy,y+frames[2]+ddy,y+frames[3]-ddy,y+frames[4]-ddy]
                xlst = [x,x,x-0.5-ddx,x-0.5-ddx,x]
            elif border.direction == DIRECTION.RIGHT:
                ylst = [y+frames[0]-ddy,y+frames[1]+ddy,y+frames[2]+ddy,y+frames[3]-ddy,y+frames[4]-ddy]
                xlst = [x+1,x+1,x+1.5+ddx,x+1.5+ddx,x+1]
            elif border.direction == DIRECTION.UP:
                xlst = [x+frames[0]-ddx,x+frames[1]+ddx,x+frames[2]+ddx,x+frames[3]-ddx,x+frames[4]-ddx]
                ylst = [y+1,y+1,y+1.5+ddy,y+1.5+ddy,y+1]
            elif border.direction == DIRECTION.DOWN:
                xlst = [x+frames[0]-ddx,x+frames[1]+ddx,x+frames[2]+ddx,x+frames[3]-ddx,x+frames[4]-ddx]
                ylst = [y,y,y-0.5-ddy,y-0.5-ddy,y]
            if 'secret' not in door.door_type.lower():
                ax.plot(xlst,ylst,color='k', linewidth=2, alpha=1, zorder=5)

        # 3. SAVE MASK: No bbox_inches='tight'!
        mask_path = self.file_path('mask.png')
        fig.savefig(self.file_path('mask.png'), facecolor='black', **save_kwargs)

        for line in inner_wall_border_line:
            line[0].remove()
            
        # Color the room.png file...
        plt.fill(*zip(*make_contour(wallborders)), 'b', alpha=1)
        if 'stairwell' in room.purpose.lower() and 'down' in room.purpose.lower():
            nborders = list(room.door_geometry_borders())
            plt.fill(*zip(*make_contour(nborders)), '#ffffff')
        else:
            plt.fill(*zip(*make_contour(borders)), '#ffffff') 
        
        # stairs (if applicable)
        if 'stairwell' in room.purpose.lower():
            if 'up' in room.purpose.lower():
                plt.fill(*zip(*make_contour(borders)), '#909090')
           # 1. Get the room center and bounds
            ax = plt.gca()
            xmin, xmax = ax.get_xlim()
            ymin, ymax = ax.get_ylim()
            center_x, center_y = (xmin + xmax) / 2, (ymin + ymax) / 2


            # 3. CALCULATE START ANGLE (Based on door placement)

            door = room.doors[0]
            xx, yy = door.borders[door.rooms.index(room)].position.point()
            direction = door.borders[door.rooms.index(room)].direction
            dx = xx - center_x
            dy = yy - center_y
            start_angle = get_start_angle(room, direction, center_x, center_y, xx, yy)
            if 'down' in room.purpose.lower():
                    start_angle = -start_angle
           
            # 4. DRAW THE STAIRS
            num_steps = 20
            
            for i in range(num_steps):
                if 'up' in room.purpose.lower():
                    delta = 1.2  - 0.5*i/num_steps
                else:
                    delta = 1.425 + 0.5*(i/num_steps)            
                floor_coords = [(xmin+delta, ymin+delta), (xmax-delta, ymin+delta), (xmax-delta, ymax-delta), (xmin+delta, ymax-delta)]
                floor_poly = Polygon(floor_coords, facecolor='none', edgecolor='none')
                max_radius = (5 - delta) * 1.414 # 1.414 ensures it reaches the corners
                ax.add_patch(floor_poly)
                theta1 = start_angle + np.radians((i + 3) * (270 / num_steps))
                theta2 = start_angle + np.radians((i + 4) * (270 / num_steps))

                if 'down' in room.purpose.lower():
                    theta1 = -theta1
                    theta2 = -theta2
                    
                # Define the 4 points of a 'wedge'
                p1 = (center_x + inner_radius * np.cos(theta1), center_y + inner_radius * np.sin(theta1))
                p2 = (center_x + max_radius * np.cos(theta1), center_y + max_radius * np.sin(theta1))
                p3 = (center_x + max_radius * np.cos(theta2), center_y + max_radius * np.sin(theta2))
                p4 = (center_x + inner_radius * np.cos(theta2), center_y + inner_radius * np.sin(theta2))

                # Use a wider range for UP: 0.2 (low) to 1.0 (high/white)
                if 'up' in room.purpose.lower():
                    val = 0.3 + (i / (num_steps - 1)) * 0.6
                else:
                    val = 0.7 - (i / (num_steps - 1)) * 0.6
                step_color = (val, val, val) # This creates the RGB grayscale tuple
                
                step = Polygon(
                    [p1, p2, p3, p4], 
                    closed=True, 
                    facecolor=step_color, 
                    edgecolor=step_color, 
                    linewidth=1, 
                    zorder=4,
                    alpha=1.0
                )
                if 'up' in room.purpose.lower():
                    step_ = Polygon(
                                [p1, p2, p3, p4], 
                                closed=True, 
                                facecolor='#ffffff', 
                                edgecolor='w', 
                                linewidth=1, 
                                zorder=4,
                                alpha=0.75
                                )
                    step_.set_clip_path(floor_poly)
                    ax.add_patch(step_)
                # Ensure it clips to the area walls
                step.set_clip_path(floor_poly)
                ax.add_patch(step)

            # make bottom stair black...
            if 'down' in room.purpose.lower():
                step = Polygon(
                    [p1, p2, p3, p4], 
                    closed=True, 
                    facecolor='k', 
                    edgecolor='k', 
                    linewidth=1, 
                    zorder=4,
                    alpha=1.0
                    )
                step.set_clip_path(floor_poly)
                ax.add_patch(step)
            # 5. DRAW THE PILLAR (To cover the center point)
            pillar = plt.Circle((center_x, center_y), inner_radius, color='k', zorder=5)
            ax.add_patch(pillar)
            # blue lines for doors
        
        for i, door in enumerate(room.doors):
            ddx, ddy = 0, 0 
            if 'Portcullis' in door.door_type:
                ddx, ddy = .2, .2
            for i, dborder in enumerate(door.borders):
                if dborder.position.point() in [block.position.point() for block in room.blocks]:
                    border = door.borders[i]
                        
            x, y = border.position.point()
            xlst, ylst = [], []
            # lower corner, other lower corner, upper 1, upper 2, lower 1 again
            frames = [0.25,0.75,.95,.05,0.25]
            if border.direction == DIRECTION.LEFT: 
                ylst = [y+frames[0]-ddy,y+frames[1]+ddy,y+frames[2]+ddy,y+frames[3]-ddy,y+frames[4]-ddy]
                xlst = [x,x,x-0.5-ddx,x-0.5-ddx,x]
            elif border.direction == DIRECTION.RIGHT:
                ylst = [y+frames[0]-ddy,y+frames[1]+ddy,y+frames[2]+ddy,y+frames[3]-ddy,y+frames[4]-ddy]
                xlst = [x+1,x+1,x+1.5+ddx,x+1.5+ddx,x+1]

            elif border.direction == DIRECTION.UP:
                xlst = [x+frames[0]-ddx,x+frames[1]+ddx,x+frames[2]+ddx,x+frames[3]-ddx,x+frames[4]-ddx]
                ylst = [y+1,y+1,y+1.5+ddy,y+1.5+ddy,y+1]
            elif border.direction == DIRECTION.DOWN:
                xlst = [x+frames[0]-ddx,x+frames[1]+ddx,x+frames[2]+ddx,x+frames[3]-ddx,x+frames[4]-ddx]
                ylst = [y,y,y-0.5-ddy,y-0.5-ddy,y]
     
            if 'secret' not in door.door_type.lower():
                curr_xlim = plt.gca().get_xlim()
                curr_ylim = plt.gca().get_ylim()
                plt.text(sum(xlst)/len(xlst), sum(ylst)/len(ylst)-0.5+(i*.2), door.door_type.split(' ')[0] + ' Door', ha='center', color='#FF0000', zorder=21)
                plt.fill(xlst, ylst, color='saddlebrown', alpha=1.0, zorder=20)
                plt.gca().set_xlim(curr_xlim)
                plt.gca().set_ylim(curr_ylim)
        
        plt.savefig(self.file_path("room.png".format(room.room_id, room.parent.info['level'])), dpi=300, bbox_inches='tight')
        if show == True:
            plt.show()
        fig.savefig(self.file_path('room.png'), **save_kwargs)
        
        if show:
            plt.show()
        else:
            plt.close(fig)
            plt.show()
    
    def render_room(self, room, show=True, showog=False):
        '''
        creates a prompt and sensds it to make the AI render the room.
        '''
        # CONFIG
        api_key = str(self.OPENROUTER_API_KEY).strip()
        input_image_path = self.file_path("room.png")
        mask_image_path = self.file_path("mask.png")  # your mask
        output_image_path = self.file_path("Rooms/{} Level {} Room {}.png".format(self.filename,
                                                                                  room.parent.info['level'],
                                                                                  room.room_id))
                                                                                  
        with Image.open(input_image_path) as img:
            # Get width and height
            ogwidth, ogheight = img.size  
        
        if showog == True:
            display(IPImage(input_image_path))
            
        def to_data_uri(path):
            with open(path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("utf-8")
            ext = path.split(".")[-1]
            return f"data:image/{ext};base64,{b64}"
        
        img_data_uri = to_data_uri(input_image_path)
        mask_data_uri = to_data_uri(mask_image_path)
        
        # PROMPT
        furnishing_list = '; '.join([a.split(': ')[1] for a in room.furnishings if any(k in a.lower() for k in ['general', 'mage', 'temple'])])
        
        newline = ''
        ld, rd, ud, dd = False, False, False, False
        lt, rt, ut, dt = '','','',''
        for i, door in enumerate(room.doors):
            for i, dborder in enumerate(door.borders):
                if dborder.position.point() in [block.position.point() for block in room.blocks]:
                    border = door.borders[i]
            
            if border.direction == DIRECTION.LEFT: 
                if 'secret' not in door.door_type.lower():
                    ld = True
                    lt = door.door_type
            elif border.direction == DIRECTION.RIGHT:
                if 'secret' not in door.door_type.lower():
                    rd = True
                    rt = door.door_type
            elif border.direction == DIRECTION.UP:
                if 'secret' not in door.door_type.lower():
                    ud = True
                    ut = door.door_type
            elif border.direction == DIRECTION.DOWN:
                if 'secret' not in door.door_type.lower():
                    dd = True
                    dt = door.door_type
        
        newline = 'DOOR COUNT RULE: Render exactly one door for every Brown polygon in room.png\n'
        ndoors = 0
        for tup in [(ud, 'NORTHERN', ut), (dd, 'SOUTHERN', dt), (ld, 'WESTERN', lt), (rd, 'EASTERN', rt)]:
            if tup[0] == False:
                newline = newline + '{} WALL CONSTRAINT: The {} Wall is solid.  There are no doors/windows/openings IN THE {} WALL.  The AI must strictly ignore any instinct to add "balance" or "symmetry" to the room.  The {} boundary is a dead-end, any door added here is a failure\n'.format(tup[1], tup[1], tup[1], tup[1])
            elif tup[0]==True:
                ndoors += 1
        if ndoors >= 1:  #replace with this...
            newline = newline + '    As there are {} brown polygons, render only {} doors. If a wall is BLUE in room.png, it is 100% solid'.format(ndoors,ndoors)
               
        floorline =  '''    FLOORS: The black grid is strictly for the horizontal floor. Do not project or continue any grid lines into the blue areas. The floor texture and grid must stop abruptly—with zero transition—at the inner black line. If a grid line hits the black boundary, it must disappear instantly.
                            Floor is only in the gridded section, and must not creep into the wall area (no floor in in the blue areas from room.png).\n"
                        '''

        if 'stairwell' in room.purpose.lower() and 'down' in room.purpose.lower():   
            floorline = '''    ARCHITECTURE:  This is a stairwell, there is no bottom, just stairs all the way down. There is only 1 set of walls, 4 walls forming a square shaft
                                THIS IS A SIMPLE SQUARE STAIRWELL.  PROHIBIT AI FROM OVERTHINKING IT
        LANDING: THE LANDING (WHITE SQUARE in room.png)  has a sharp 90-DEGREE VERTICAL DROP. Prohibit any transitional floor. 
                                - the landing is only the 5ft square landing in the corner of the shaft
                                - The stair width must fill 100% of the horizontal space between the central pillar and the outer walls.
                                - The landing is in one corner of the room, there are two sides where it is bound by the walls
                                - If there are any Landing pixels outside the white square in room.png, the render is a failure\n '''

        prompt = ( 
            f"IMAGE **EDITING** TASK: Cinematic Schematic Render.\n\n"
            f"STRICT MASK RULE: Use MASK.png as a physical stencil. \n"
            f"SAFETY OVERRIDE: The black pixels in MASK.png are a hard boundary.\n" # If a pixel is black in the mask, do not render any light, shadow, or texture there. Keep it pure black."
            f"    The thick black lines are the 'clipping edge.' If a pixel is outside that central area, it MUST be the vertical wall material, never the floor material.\n"
            #f"- BLACK pixels in MASK.png are FROZEN. Do not change them.\n"
            # f"- WHITE pixels in MASK.png are the ONLY editable zones. \n\n"
            f"PIXEL LOGIC (THE LEGEND):\n Interpret the colors in room.png with absolute mathematical priority:\n   BROWN POLYGON: This is the ONLY location for a door. If you see Brown, render a door. \n   BLUE AREA: This is SOLID WALLS. No exceptions. No openings.\n   RED LABELS: These are coordinates for door types. Delete the text after reading.\n"
            f"1. ARCHITECTURE: The blue areas are VERTICAL WALLS that act as a 3D cookie-cutter. They physically overlap and HIDE the floor. There is no grid on the walls. The floor does not 'meet' the wall; it is simply cut off by the wall. Do not render any bevel, shadow-line, or ledge where the floor hits the blue area\n."
            f"    ARCHITECTURE: The BLUE areas represent SOLID, IMPENETRABLE WALLS. If a wall does not have a brown door polygon, it is a single, continuous, and unbroken wall.\n"
            #f"2. MOOD & STYLE: {room.purpose} ({room.state})  Use Even neutral lighting (No directional shadows separating objects) and realistic textures.\n"
            f"2. MOOD & STYLE: {room.purpose} ({room.state})  Use cinematic lighting and realistic textures.\n"
            f"{floorline}\n"
            f"        Texture: {room.parent.info['floors']}.\n"  
            f"         -Treat the black boundary line as a physical barrier. THIS Texture must be 'clipped' by the wall mask. Do not anti-alias or blend this area into the wall.\n"
            f"    WALLS (BLUE in ROOM.png): Vertical inner wall faces\n"
            f"        Texture: {room.parent.info['walls']}. Thicker black line is top of wall.\n"
            f"        These are physically separate from the floor. Even if the textures are identical, the wall grain must be vertical and the floor grain must be horizontal. The wall texture MUST NOT touch the floor grid.\n"
            f"    Walls should start at the black line around the gridded section.\n"
            f"3. DOOR ANCHORS: ONLY render doors where you see a BROWN POLYGON and a RED LABEL. If an area is BLUE, it is a SOLID WALL\n"
            f"    Render a closed medieval door made of the labeled material exactly inside the brown gaps. If a wall is solid blue in the mask, it is a PERMANENT wall.\n"
            f"    The Brown areas are gaps in the walls filled with a door.  Doors must be INSIDE the walls like real doors\n"
            f"    Remove the red labels\n"
            f"{newline}\n"
            f"    Do not add 'cinematic' door frames or gaps where they are not drawn in room.png.\n"
            f"4. DETAILS: {furnishing_list} \n"
            f"   - MANDATORY SIZE: Scale items accordingly to one grid square being 5ft.\n"
            f"   - VIEW: Strict 90-degree TOP-DOWN. Objects must look like flat floor-details, not 3D models.\n"
            f"5. NO EXTRA OPENINGS: The layout is a closed system.\nNo extra gridlines.  Do not make up your own gridlines.\n"
            f"   NO DOORS ON THE FLOOR, NOTHING OUTSIDE THE WALLS, NO EXTRA DOORS THAT ARE NOT IN THE MASK\n"
            f"   USE REALISTIC TEXTURES\n"
            f" DO NOT DRAW BLACK LINES FROM mask.png on the final image, especially wall corner lines\n"
            f"      only lines from room.png are to be reprooduced on final image\n"
            f"    Do not draw door labels on the map\n\n"
            f"  Look at the provided image room.png. ONLY render doors on the BROWN pixels. If a pixel is BLUE, it is a solid wall with no gaps.  If a pixel is white, it is a floor.\n"
            f"    VIOLATION LOGIC: Any door frame, handle, gap, or recessed area rendered on a Blue pixel is a total failure of the schematic task.\n"
            f"OUTPUT: ONLY the base64 data URI. No text."
        )
        
        # save the prompt for debugging
        room.image_prompt = prompt
        
        
        # API REQUEST
        payload = {
            "model": "google/gemini-2.5-flash-image",  # use a multimodal Vision model
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": img_data_uri}},
                        {"type": "image_url", "image_url": {"url": mask_data_uri}},
                    ],
                }
            ],
        }
        
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        

        # PROCESS OUTPUT
        if response.status_code == 200:
            res = response.json()
            msg = res["choices"][0]["message"]
        
            # Find base64 image in the response
            img_url = None
            if "images" in msg and len(msg["images"]) > 0:
                img_url = msg["images"][0].get("image_url", {}).get("url")
        
            # If not in images, maybe in content
            if not img_url:
                content = msg.get("content", "")
                if "base64," in content:
                    img_url = content.split("base64,")[-1]
        
            if img_url:
                raw_b64 = img_url.split("base64,")[-1]
                with open(output_image_path, "wb") as f:
                    f.write(base64.b64decode(raw_b64))
                print("✅ Saved edited image:", output_image_path)
                
                #resize it for roll20 or other VTTs
                with Image.open(output_image_path) as img:
                    resized_img = img.resize((ogwidth, ogheight))
                    resized_img.save(output_image_path)
                    
                if show == True:
                    display(IPImage(filename=output_image_path))
                
            else:
                print("⚠️ No image returned — model may have replied with text only.")
        else:
            print("❌ API Error", response.status_code, response.text)

    def edit_room_image(self, edits, show=True):
        '''
        Need to be specific and, if mentioning doors, spoecify to leave the other doors alone.
        
        'Replace the 1 door on the Northern Wall (just the top door) with bare wall.  Leave the other 3 doors intact.'
        '''
        room = self.current_room
        api_key = str(self.OPENROUTER_API_KEY).strip()
        image_path = self.file_path("Rooms/{} Level {} Room {}.png".format(self.filename,
                                                                                  room.parent.info['level'],
                                                                                  room.room_id))

        edits = ' -' + '\n-'.join(edits.split('.'))
        with Image.open(image_path) as img:
            # Get width and height
            ogwidth, ogheight = img.size  

        if ogwidth >= ogheight:
            width = 1024
            height = int((ogheight*width)/ogwidth)
        else:
            height = 1024
            width = int((height*ogwidth)/ogheight)

        with Image.open(image_path) as img:
            resized_img = img.resize((width, height))
            resized_img.save(image_path)

        def to_data_uri(path):
                with open(path, "rb") as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode("utf-8")
                ext = path.split(".")[-1]
                return f"data:image/{ext};base64,{b64}"

        img_data_uri = to_data_uri(image_path)

        prompt = '''
        Using the image provided, {}
        '''.format(edits)
        # API REQUEST
        payload = {
            "model": "google/gemini-2.5-flash-image",  # use a multimodal Vision model
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": img_data_uri}},
                    ],
                }
            ],
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        
        # PROCESS OUTPUT
        if response.status_code == 200:
            res = response.json()
            msg = res["choices"][0]["message"]
        
            # Find base64 image in the response
            img_url = None
            if "images" in msg and len(msg["images"]) > 0:
                img_url = msg["images"][0].get("image_url", {}).get("url")
        
            # If not in images, maybe in content
            if not img_url:
                content = msg.get("content", "")
                if "base64," in content:
                    img_url = content.split("base64,")[-1]
        
            if img_url:
                raw_b64 = img_url.split("base64,")[-1]
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(raw_b64))
                print("✅ Saved edited image:", image_path)
                
                #resize it for roll20 or other VTTs
                with Image.open(image_path) as img:
                    resized_img = img.resize((ogwidth, ogheight))
                    resized_img.save(image_path)
                    
                if show == True:
                    display(IPImage(filename=image_path))
                
            else:
                print("⚠️ No image returned — model may have replied with text only.")
        else:
            print("❌ API Error", response.status_code, response.text)
 
class Roll20Automator:
    def __init__(self, user_data_dir="./roll20_session"):
        self.user_data_dir = user_data_dir
        self.playwright = None
        self.context = None
        self.page = None

    async def connect(self):
        """Starts at Google to establish a clean session, then you navigate."""
        print("Launching Browser...")
        self.playwright = await async_playwright().start()
        
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=False,
            # Standard arguments to look like a normal browser
            args=["--disable-blink-features=AutomationControlled"],
            viewport={'width': 1920, 'height': 1080}
        )
        
        self.page = self.context.pages[0]
        
        # Start at Google as requested
        print("Navigating to Google...")
        await self.page.goto("https://www.google.com")
        
        print("\n--- MANUAL STEPS ---")
        print("1. In the browser window, go to Roll20.net and log in.")
        print("2. Launch your game: ")
        print("3. Once the map is loaded, come back here to run your upload.")
        
    async def close(self):
        """Clean up resources."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        
                    
    async def send_chat(self, chat_message):
        '''
        This lets us send commands to API MODs
        '''
        # 1. Find the Roll20 Editor tab among your open pages
        editor_page = next((p for p in self.context.pages if "editor" in p.url), None)
        
        if not editor_page:
            print("❌ Editor tab not found. Make sure Roll20 is open.")
            return
    
        # 2. Select the chat input textarea
        # Force click the Chat Tab using JavaScript evaluation
        await editor_page.evaluate('document.querySelector("a[href=\'#textchat\']").click()')
        chat_input = editor_page.locator('#textchat-input textarea')
    
        # 3. Ensure it's ready and click/focus it
        await chat_input.wait_for(state="visible")
        await chat_input.click()
    
        # 4. Type the message
        await chat_input.fill("") # Clear it first
        await chat_input.fill(chat_message)
    
        # 5. Press Enter to send
        await editor_page.keyboard.press("Enter")
        print(f"Sent to chat: {chat_message}")
    
    async def make_map(self, room):
        '''
        !map Room Name||URL||Width||Height||Description
        '''
        image_path = room.parent.parent.file_path('Rooms\\{} Level {} Room {}.png'.format(room.parent.parent.filename, room.parent.level, room.room_id))
        room_name = image_path.replace('Rooms/','').replace('.png','')
        image_url = room.imgsrc
        description = room.description
        
        await self.send_chat(f'!map ||{room_name}||{image_url}||{int(room.width_px/70)}||{int(room.height_px/70)}||{description.replace('\n','|n').replace('\r', '|n')}')

    async def upload_image(self, room):
        
        file_path = room.parent.parent.file_path('Rooms\\{} Level {} Room {}.png'.format(room.parent.parent.filename, room.parent.level, room.room_id))
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return
    
        # 1. Read dimensions locally with PIL
        try:
            with Image.open(file_path) as img:
                width_px, height_px = img.size
                room.width_px = width_px
                room.height_px = height_px
                room.grid_w = max(1, round(width_px / 70))
                room.grid_h = max(1, round(height_px / 70))
                print(f"📐 File Dimensions: {width_px}x{height_px}px -> Grid: {room.grid_w}x{room.grid_h}")
        except Exception as img_err:
            print(f"⚠️ Could not read image dimensions: {img_err}")
            room.grid_w = getattr(room, 'grid_w', 10) or 10
            room.grid_h = getattr(room, 'grid_h', 10) or 10
    
        editor_page = next((p for p in self.context.pages if "editor" in p.url), None)
        if not editor_page:
            print("❌ Editor tab not found.")
            return
    
        file_name = os.path.basename(file_path)
        clean_base_name = os.path.splitext(file_name)[0]
        print(f"Uploading: {file_name}...")
    
        captured_url = None
    
        # Track network responses specific to AWS/d20 S3 upload endpoints
        async def handle_response(response):
            nonlocal captured_url
            url = response.url
            if ("files.d20.io/images/" in url or "s3.amazonaws.com" in url) and ("thumb" in url or "max" in url):
                captured_url = url
    
        editor_page.on("response", handle_response)
    
        try:
            # 2. Open Art Library & Upload Dialog
            await editor_page.evaluate('document.querySelector("#ui-id-2").click()')
            await asyncio.sleep(0.3)
            await editor_page.evaluate('document.querySelector("#userlibrary button.showuploaddialog").click()')
            await asyncio.sleep(0.3)
    
            # 3. Snapshot existing preview img src if present
            preview_img = editor_page.locator(".ui-dialog:visible .file-uploader img, .ui-dialog:visible .uploading-list img").first
            old_src = await preview_img.get_attribute("src") if await preview_img.count() > 0 else None
    
            # 4. Perform File Upload
            async with editor_page.expect_file_chooser() as fc_info:
                await editor_page.click('.file-uploader__dropzone')
                file_chooser = await fc_info.value
                await file_chooser.set_files(file_path)
    
            # 5. Wait for preview src to change from the old src
            for _ in range(15):
                await asyncio.sleep(0.4)
                if await preview_img.count() > 0:
                    new_src = await preview_img.get_attribute("src")
                    if new_src and new_src != old_src and "http" in new_src:
                        captured_url = new_src
                        break
    
            # 6. Format and store clean URLs
            if captured_url:
                clean_thumb = captured_url.split('?')[0].replace("max.png", "thumb.png").replace("max.jpg", "thumb.jpg")
                clean_max = clean_thumb.replace("thumb.png", "max.png").replace("thumb.jpg", "max.jpg")
    
                room.image_json = {
                    "thumb": clean_thumb,
                    "imgsrc": clean_max,
                    "id": clean_base_name,
                    "grid_w": room.grid_w,
                    "grid_h": room.grid_h
                }
                room.imgsrc = clean_thumb
                print(f"✅ Captured Target Map URL: {clean_thumb}")
            else:
                print("⚠️ Upload completed, but target image URL was not updated.")
    
        except Exception as e:
            print(f"❌ Upload error: {e}")
    
        finally:
            editor_page.remove_listener("response", handle_response)
            
            # Close dialog
            try:
                close_button = editor_page.locator(".ui-dialog-titlebar-close").last
                if await close_button.is_visible():
                    await close_button.click()
                else:
                    await editor_page.keyboard.press("Escape")
            except Exception:
                pass
            await asyncio.sleep(0.3)

##############
# Enumerations
##############

class DIRECTION(enum.Enum):
    '''
    An enum that sets direction
    '''
    LEFT = 1
    RIGHT = 2
    UP = 3
    DOWN = 4

#######
# Utils
#######

def monster_reaction(modifier = 0):
    '''
    old school monster reaction table
    
    2d6	Result
    2 or less	Attacks
    3–5	Hostile, may attack
    6–8	Unsure, confused, cautious
    9–11	Indifferent, may negotiate
    12 or more	Eager, friendly
    '''
    roll = random.randint(1,6)
    roll = roll + random.randint(1,6) #seperated to avoid the same seed
    roll = roll + modifier
    
    if roll <= 2:
        return 'The Monsters Attack the Players'
    elif roll >= 3 and roll <= 5:
        return 'They are Hostile, may attack'
    elif roll >= 6 and roll <= 8:
        return 'They are Unsure, confused, cautious'
    elif roll >= 9 and roll <= 11:
        return 'They are Indifferent, may negotiate'
    elif roll >=12:
        return 'They are Eager, friendly'

def points_at_circle(x, y, radius):
    points = set()

    for i in range(radius + 1):
        points.add((x + i, y + (radius - i)))
        points.add((x + i, y - (radius - i)))
        points.add((x - i, y + (radius - i)))
        points.add((x - i, y - (radius - i)))

    return points

def restore_path(path_map, point):
    path = []

    while point is not None:
        path.append(point)
        point = path_map[point]

    path.reverse()

    return path

def find_path(point_from, point_to, filled_cells, max_path_length):
    '''
    '''
    index = 0

    heap = [(0, index, point_from, None)]

    visited_points = {}

    path_map = {}

    while True:

        cost, _, point, prev_point = heapq.heappop(heap)

        path_map[point] = prev_point

        if max_path_length <= cost:
            return None, None

        if point == point_to:
            return cost, restore_path(path_map, point_to)

        visited_points[point] = cost

        for next_point in point.neighbours():
            if next_point in visited_points:
                continue

            if next_point in filled_cells:
                continue

            index += 1
            heapq.heappush(heap, (cost + 1, index, next_point, point))

    return None, None

def make_contour(segments):

    segments = list(segments)

    line = list(segments.pop())

    while True:

        end_point = line[-1]

        for segment in segments:
            if end_point == segment[0]:
                line.append(segment[1])
                segments.remove(segment)
                break
        else:
            break

    return line

def get_distance(tup1, tup2):
    x = tup2[0]-tup1[0]
    y = tup2[1]-tup1[1]
    return (x**2 + y**2)**(0.5)
    
def direction_to_compass(direction):
    if direction == DIRECTION.LEFT:
        return 'West'
    elif direction == DIRECTION.RIGHT:
        return 'East'
    elif direction == DIRECTION.UP:
        return 'North'
    elif direction == DIRECTION.DOWN:
        return 'South'
    else:
        return direction
    
def make_contour(segments):

    segments = list(segments)

    line = list(segments.pop())

    while True:

        end_point = line[-1]

        for segment in segments:
            if end_point == segment[0]:
                line.append(segment[1])
                segments.remove(segment)
                break
        else:
            break

    return line

def make_diagonal_wall_border(borders):
    x,y = borders[0].position.point()
    dx,dy = 0,0
    ddx, ddy = 0, 0
    for border in borders:
        if border.direction == DIRECTION.LEFT: 
            dx = dx-1
        elif border.direction == DIRECTION.RIGHT:
            dx = dx+1
            ddx = 1
        elif border.direction == DIRECTION.UP:
            dy = dy+1
            ddy = 1
        elif border.direction == DIRECTION.DOWN:
            dy = dy-1
    return [(x+ddx,y+ddy),(x+dx+ddx,y+dy+ddy)]

def make_fakeroom(room):
    new_borders = []
    for block in room.blocks:
        new_borders.append(block.position.point())
        a = [border for border in block.borders.values() if border.internal == False]
        if len(a) > 0:
            x, y = block.position.point()
            changes = [[0,0] for border in a]
            for i, border in enumerate(a):
                if border.direction == DIRECTION.LEFT: 
                    changes[i][0] = -1
                elif border.direction == DIRECTION.RIGHT:
                    changes[i][0] = 1
                elif border.direction == DIRECTION.UP:
                    changes[i][1] = 1
                elif border.direction == DIRECTION.DOWN:
                    changes[i][1] = -1
            actual_changes = []
            for i, change in enumerate(changes):
                actual_changes.append(tuple(change))
                for ochange in changes[i+1:]:
                    actual_changes.append((change[0]+ochange[0],change[1]+ochange[1]))
            changes = list(set(actual_changes))
            [new_borders.append((x+a[0],y+a[1])) for a in changes]
    new_borders = list(set(new_borders))
    # make a fakeroom to set the borders...
    fakeroom = Room(parent=room.parent, is_exit=True)
    fakeroom.blocks = []
    for point in new_borders:
        new_block = Block(Position(point[0], point[1]))
        for block in fakeroom.blocks:
                block.sync_borders_with(new_block)
        fakeroom.blocks.append(new_block) 
    return fakeroom

def perpendicular(a, b):
    horizontal = {DIRECTION.LEFT, DIRECTION.RIGHT}
    vertical   = {DIRECTION.UP, DIRECTION.DOWN}
    return ((a.direction in horizontal and b.direction in vertical) or
            (a.direction in vertical and b.direction in horizontal))

def make_diagonals(room):
    diagonals = []

    for block in room.blocks:
        borders = [b for b in block.borders.values() if not b.internal]

        # Check ALL pairs
        for i in range(len(borders)):
            for j in range(i + 1, len(borders)):
                a = borders[i]
                b = borders[j]

                if perpendicular(a, b):
                    diagonals.append(
                        make_diagonal_wall_border([a, b])
                    )

    return diagonals    
 
def get_figsize_from_wallborders(wallborders, dpi=70, pixels_per_unit=70, padding_units=1):
    all_points = [pt for segment in wallborders for pt in segment]
    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]

    # If room is 8x8, xmax-xmin = 8
    xmin, xmax = min(xs) - padding_units, max(xs) + padding_units
    ymin, ymax = min(ys) - padding_units, max(ys) + padding_units

    x_units = xmax - xmin # This should be 10
    y_units = ymax - ymin # This should be 10

    # 10 units * 70 px/unit = 700px
    # 700px / 70 dpi = 10 inches
    figsize = (x_units * pixels_per_unit / dpi, y_units * pixels_per_unit / dpi)

    return figsize, (xmin, xmax), (ymin, ymax)
    
def get_start_angle(room, direction, center_x, center_y, xx, yy):
    # Calculate door position relative to your specific center
    dx = xx - center_x
    dy = yy - center_y
    
    # We use the signs of dx and dy to find the visual quadrant.
    # If the output is 180 off, we swap the logic to match the plot's Y-inversion.
    
    if direction == DIRECTION.LEFT:
        # Southern Block on West wall
        # If dy < 0 is visually 'South' in your plot:
        angle = 225 if dy < 0 else 135
        
    elif direction == DIRECTION.RIGHT:
        # Southern Block on East wall
        angle = 315 if dy < 0 else 45
        
    elif direction == DIRECTION.UP:
        # North wall: check relative left/right (dx)
        angle = 135 if dx < 0 else 45
        
    elif direction == DIRECTION.DOWN:
        # South wall: check relative left/right (dx)
        angle = 225 if dx < 0 else 315
    else:
        angle = 0.0

    return np.deg2rad(angle)

def border_wall(border):
    x,y = border.position.point()
    if border.direction == DIRECTION.LEFT: 
        return [[(x-1,y+(i-1)), (x-1, y+i)] for i in range(3)]
    elif border.direction == DIRECTION.RIGHT:
        return [[(x+2,y+(i-1)), (x+2, y+i)] for i in range(3)]
    elif border.direction == DIRECTION.UP:
        return [[(x+(i-1),y+2), (x+i, y+2)] for i in range(3)]
    elif border.direction == DIRECTION.DOWN:
        return [[(x+(i-1),y-1), (x+i, y-1)] for i in range(3)]    

def get_door_border(room, door):
    for i, dborder in enumerate(door.borders):
        if dborder.position.point() in [block.position.point() for block in room.blocks]:
            border = door.borders[i]
    return border
   
def simple_path(tup1, tup2):
    current = (tup1[0], tup1[1])
    path = []
    while current != tup2:
        dx = 0
        dy = 0
        if current[0] != tup2[0]:
            if current[0] < tup2[0]:
                dx = 1
            else:
                dx = -1
        if current[1] != tup2[1]:
            if current[1] < tup2[1]:
                dy = 1
            else:
                dy = -1
        current = (current[0]+dx, current[1]+dy)
        if current != tup2:
            path.append(Position(x=current[0], y=current[1]))
    return path

##############
# Core classes
##############

class Position():
    '''
    position is a tuple, (x, y)
    '''

    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    def __getstate__(self):
        # Capture everything
        return self.__dict__.copy()
    
    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return (self.x, self.y) == (other.x, other.y)

    def __ne__(self, other):
        return not self.__eq__(other)

    def neighbours(self):
        '''
        finds all neighboring blocks that share a border with the block in question...
        '''
        return {Position(self.x - 1, self.y),
                Position(self.x, self.y - 1),
                Position(self.x + 1, self.y),
                Position(self.x, self.y + 1)}

    def area(self):
        '''
        Not sure why this is called "area"
        grabs the blocks that border on all sides...
        '''
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                yield Position(self.x + dx, self.y + dy)

    def move(self, dx, dy):
        '''
        grabs position dx, dy away for moving the block
        '''
        return Position(self.x + dx, self.y + dy)
        
    def rotate_clockwise(self):
        return Position(self.y, -self.x)

    def point(self):
        '''
        returns the position as a tuple
        '''
        return (self.x, self.y)

class Border():
    '''
    finds the borders of a room
    '''
   
    def __init__(self, position, direction):
        self.position = position
        self.direction = direction
        self.internal = False
        self.can_has_door = False
        self.used = False
        self.door = None

    def __getstate__(self):
        # Capture everything
        return self.__dict__.copy()
        
    def __eq__(self, other):
        return (self.position, self.direction) == (other.position, other.direction)

    def __ne__(self, other):
        return not self.__eq__(other)
    
    def is_mirrored(self, other_border):
        check_direction = None
        if self.direction == DIRECTION.LEFT:
           check_direction = DIRECTION.RIGHT
        elif self.direction == DIRECTION.RIGHT:
            check_direction = DIRECTION.LEFT
        elif self.direction == DIRECTION.UP:
            check_direction = DIRECTION.DOWN
        elif self.direction == DIRECTION.DOWN:
            check_direction = DIRECTION.UP
            
        if other_border.direction == check_direction:
            return True
        else:
            return False
            
    def mirror(self):
        '''
        mirrors the border position
        '''
        if self.direction == DIRECTION.LEFT:
            return Border(self.position.move(-1, 0), DIRECTION.RIGHT)

        if self.direction == DIRECTION.RIGHT:
            return Border(self.position.move(1, 0), DIRECTION.LEFT)

        if self.direction == DIRECTION.UP:
            return Border(self.position.move(0, 1), DIRECTION.DOWN)

        if self.direction == DIRECTION.DOWN:
            return Border(self.position.move(0, -1), DIRECTION.UP)

    def geometry_borders(self):
        '''
        creates the geometry of the borders
        '''
        if self.direction == DIRECTION.LEFT:
            return [self.position.move(0, 0).point(),
                    self.position.move(0, 1).point()]

        if self.direction == DIRECTION.RIGHT:
            return [self.position.move(1, 1).point(),
                    self.position.move(1, 0).point()]

        if self.direction == DIRECTION.UP:
            return [self.position.move(0, 1).point(),
                    self.position.move(1, 1).point()]

        if self.direction == DIRECTION.DOWN:
            return [self.position.move(1, 0).point(),
                    self.position.move(0, 0).point()]
        
    def wall_geometry_borders(self):
        '''
        creates the geometry of the wall borders
        '''
        
        if self.direction == DIRECTION.LEFT:
            return [self.position.move(-1, -1).point(),
                    self.position.move(-1, 0).point()]

        if self.direction == DIRECTION.RIGHT:
            return [self.position.move(2, 2).point(),
                    self.position.move(2, 1).point()]

        if self.direction == DIRECTION.UP:
            return [self.position.move(1, 2).point(),
                    self.position.move(2, 2).point()]

        if self.direction == DIRECTION.DOWN:
            return [self.position.move(0, -1).point(),
                    self.position.move(-1, -1).point()]

    def rotate_clockwise(self):
        '''
        As it says on the tin
        '''
        self.position = self.position.rotate_clockwise()

        if self.direction == DIRECTION.LEFT:
            self.direction = DIRECTION.UP

        elif self.direction == DIRECTION.RIGHT:
            self.direction = DIRECTION.DOWN

        elif self.direction == DIRECTION.UP:
            self.direction = DIRECTION.RIGHT

        elif self.direction == DIRECTION.DOWN:
            self.direction = DIRECTION.LEFT
            
    def move(self, dx, dy):
        '''
        moves it dx, dy
        '''
        self.position = self.position.move(dx, dy)

    def connection_point(self):
        '''
        finds a connection point...
        '''
        segment = self.geometry_borders()

        return ((segment[0][0] + segment[1][0]) / 2,
                (segment[0][1] + segment[1][1]) / 2)
        
class Block():
    '''
    position
    borders
    '''
    
    def __init__(self, position):
        self.position = position

        self.borders = {DIRECTION.RIGHT: Border(position, DIRECTION.RIGHT),
                        DIRECTION.LEFT: Border(position, DIRECTION.LEFT),
                        DIRECTION.UP: Border(position, DIRECTION.UP),
                        DIRECTION.DOWN: Border(position, DIRECTION.DOWN)}
    
    def __getstate__(self):
        # Capture everything
        return self.__dict__.copy()
        
    def geometry_borders(self):
        '''
        returns the borders that are external vs internal to the room
        '''
        return [border.geometry_borders()
                for border in self.borders.values()
                if not border.internal]
                
    def wall_geometry_borders(self):
        '''
        returns the borders that are external vs internal to the room
        '''
        return [border.wall_geometry_borders()
                for border in self.borders.values()
                if not border.internal]
                
    
    def grid_borders(self):
        '''
        returns the internal borders for drawing the grid
        '''
        return [border.geometry_borders()
                for border in self.borders.values() if border.internal]
                

    def sync_borders_with(self, block):
        '''
        checks if borders are internal
        '''
        for own_border in self.borders.values():
            for other_border in block.borders.values():
                if own_border.mirror() == other_border:
                    own_border.internal = True
                    other_border.internal = True

    def move(self, dx, dy):
        self.position = self.position.move(dx, dy)

        for border in self.borders.values():
            border.move(dx, dy)
            
    def rotate_clockwise(self):
        self.position = self.position.rotate_clockwise()

        for border in self.borders.values():
            border.rotate_clockwise()

        self.borders = {border.direction: border for border in self.borders.values()}

class Room():
    '''
    A collection of blocks...
    '''
    
    def __init__(self, parent, position=Position(0,0), hallway=False, stairs=None, is_exit=False):      
        self.blocks = [Block(position)]
        self.color = 'gray'  #random_color()
        self.doors = []
        self.is_exit = is_exit
        self.purpose = ''
        self.state = ''
        self.contents = ''
        self.parent = parent
        self.room_id = len(self.parent.rooms)
        self.hallway = hallway
        self.stairs = stairs
        self.monster = ''
        self.treasure  = ''
        self.furnishings = []
        self.traps = ''
        self.hazards = ''
        self.stock_room(hallway)
        self.description = ''
        self.quest = ''
        self.old_description = ''
        self.captive_name = ''
        self.ceiling_height = '10 ft'
        
    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove the parent to prevent circular recursion during pickle
        if 'parent' in state:
            del state['parent']
        # Capture everything
        return self.__dict__.copy()
            
    def __setstate__(self, state):
        self.__dict__.update(state)
        # Restore the back-references safely
        for door in getattr(self, 'doors', []):
            # Ensure the 'rooms' list exists on the door before appending
            if not hasattr(door, 'rooms'):
                door.rooms = []
            # Only add self if it's not already there to avoid duplicates on double-loads
            if self not in door.rooms:
                door.rooms.append(self)
        
    def block_positions(self):
        return {block.position for block in self.blocks}

    def area_positions(self):
        area = set()

        for position in self.block_positions():
            area |= set(position.area())

        return area
   
    def allowed_new_block_positions(self):
        '''
        If using expand to randomly make a room, determines where
        a block can go
        
        Cahnegd from a set to a list to make more regular shaped rooms
        '''
        allowed_positions = list()

        for block in self.blocks:
            [allowed_positions.append(a) for a in list(block.position.neighbours()) if a not in list(self.block_positions())]


        return allowed_positions
               
    def expand(self):
        '''
        Randomly adds a block to the border of another block in the room
        '''
        # The below makes the choice random...
        # new_position = random.choice(list(self.allowed_new_block_positions()))
        # we want more regular shaped rooms...
        possibilities = []
        for item, counts in collections.Counter(list(self.allowed_new_block_positions())).items():
            # have each block appear the square of the number of neighbors
            for i in range(counts**counts):  
                possibilities.append(item)

        # Still random, but more likely to fill properly
        new_position = random.choice(possibilities)
        new_block = Block(new_position)

        for block in self.blocks:
            block.sync_borders_with(new_block)

        self.blocks.append(new_block)
 
    def geometry_borders(self):
        '''
        gives outer borders of room
        '''
        borders = []

        for block in self.blocks:
            borders.extend(block.geometry_borders())

        return borders
    
    def door_geometry_borders(self):
        '''
        gives outer borders of any square with a door on it
        '''
        borders = []
        

        block_positions = [door.borders[door.rooms.index(self)].position.point() for door in self.doors]
        for block_position in [door.borders[door.rooms.index(self)].position.point() for door in self.doors]:
            for block in [block for block in self.blocks if block.position.point() == block_position]:
                borders.extend([a.geometry_borders() for a in block.borders.values()])

        return borders
        
    def wall_geometry_borders(self):
        '''
        gives outer borders of room
        '''
        borders = []

        for block in self.blocks:
            borders.extend(block.wall_geometry_borders())

        return borders
              
    def grid_borders(self):
        '''
        gives inner borders of the blocks in the room so a grid may be drawn
        '''
        borders = []

        for block in self.blocks:
            borders.extend(block.grid_borders())

        return borders

    def rectangle(self):
        '''
        finds the corners of the rectangle that contains the randomly shapoed room
        '''
        positions = self.block_positions()

        min_x, max_x, min_y, max_y = 0, 0, 0, 0

        for position in positions:
            min_x = min(position.x, min_x)
            min_y = min(position.y, min_y)
            max_x = max(position.x, max_x)
            max_y = max(position.y, max_y)

        return min_x, min_y, max_x, max_y

    def has_holes(self):
        '''
        finds holes in the room...
        '''
        min_x, min_y, max_x, max_y = self.rectangle()

        block_positions = self.block_positions()

        all_positions = set()

        # add additional empty cells around rectangle
        # to guaranty connectedness
        for x in range(min_x - 1, max_x + 2):
            for y in range(min_y - 1, max_y + 2):
                all_positions.add(Position(x, y))

        all_positions -= block_positions

        first_position = next(iter(all_positions))

        queue = collections.deque()

        queue.append(first_position)

        while queue:
            position = queue.popleft()

            if position not in all_positions:
                continue

            queue.extend(position.neighbours())

            all_positions.remove(position)

        return bool(all_positions)

    def is_intersect(self, room):
        return bool(self.area_positions() & room.block_positions())

    def move(self, dx, dy):
        for block in self.blocks:
            block.move(dx, dy)

    def rotate_clockwise(self):
        for block in self.blocks:
            block.rotate_clockwise()
            
    def borders(self):
        for block in self.blocks:
            for border in block.borders.values():
                yield border

    def door_borders(self):
        for border in self.borders():
            if border.can_has_door:
                yield border

    def place_doors(self, number, trapped=False, t_pass=False):
        borders = [border
                           for border in self.borders()
                           if not border.internal]
                           
        number = min(int(len(borders)/3), number)
        # find extreme borders...
        max_x, max_y = borders[0].position.point()
        min_x, min_y = borders[0].position.point()
        min_distance_to_center = 90001
        
        
        # Get the min/max
        x_lst = [border.position.point()[0] for border in borders]
        y_lst = [border.position.point()[1] for border in borders]
        
        max_x = max(x_lst)
        min_x = min(x_lst)
        max_y = max(y_lst)
        min_y = min(y_lst)    
        mid_x = int((max_x + min_x)/2)
        mid_y = int((max_y + min_y)/2)
        
        check_borderx = []
        check_bordery = []
        
        #large rooms/long hallways
        if max_x - min_x >= 12:
            check_borderx.append(mid_x + int(mid_x/2))
            check_borderx.append(mid_x - int(mid_x/2))
        if max_y - min_y >= 12:
            check_bordery.append(mid_y + int(mid_y/2))
            check_bordery.append(mid_y - int(mid_y/2))
            
        if self.hallway == True:
            check_borderx.append(min_x)
            check_borderx.append(max_x)
            check_bordery.append(min_y)
            check_bordery.append(max_y)
        
        if mid_x%2 == 0:
            check_borderx.append(mid_x+1)
        if mid_y%2 == 0:
            check_bordery.append(mid_y+1)
        check_bordery.append(mid_y)
        check_borderx.append(mid_x)
            
        valid_borders = []
        for border in borders:
            x, y = border.position.point()
            # we want ends of hallways and middle of rooms
            if ((x in check_borderx or y in check_bordery) and self.hallway == False) or (self.hallway and x in check_borderx and y in check_bordery):
                valid_borders.append(border)
            # lets try to make sure the dungeon centers...   
            if get_distance((0,0), (x,y)) >= min_distance_to_center+1 and border in valid_borders:
                valid_borders.append(border)
            if (x == max_x or y ++ max_y) and self.hallway and border in valid_borders:
                for _ in range(3):  #we want ends of hallways to have doors, otherwise why?
                    valid_borders.append(border)

        neighbors = set()
        directions = set()

        while len(self.doors) < number and len(valid_borders) > 0:
            border = random.sample(valid_borders, 1)[0]
            check_position = border.position
            check_direction = border.direction
            # want 1 per wall unless we have a lot...
            if len(list(directions)) > 4 or check_direction not in directions:
                border.can_has_door = True
                door = Door(parent=self)
                door.borders.append(border)
                door.rooms.append(self)
                border.door = door
                self.doors.append(door)
                for i in range(3):
                    for j in range(3):
                        neighbors.add((check_position.point()[0]+i-1, check_position.point()[1]+j-1))
            else:  # remove it, even though it could be valid later... [prevent infinite loop]
                neighbors.add(check_position.point()) 
            valid_borders = [a for a in valid_borders if a.position.point() not in neighbors]
            directions.add(check_direction)
            if trapped == True:
                door.trapped = True        
                               
    def make_circle(self, diameter):
        '''
        Starts a circle from the firs position...
        
        start = self.blocks[0].position.point()
        center = start
        for i in range(-int(diameter/10)-2,int(diameter/10)+2,1):
            for j in range(-int(diameter/10)-2,int(diameter/10)+2,1):
                new_position = Position(start[0]+i,start[1]+j)
                if (center[0]-new_position.point()[0])**2 + (center[1]-new_position.point()[1])**2 < (diameter/10)**2:
                    new_block = Block(new_position)
                    for block in self.blocks:
                        block.sync_borders_with(new_block)
                    self.blocks.append(new_block)
        '''
        # killing circular rooms because they fail to render, replacing wit squares.
        self.make_rectangle(diameter, diameter)
        
    def make_rectangle(self, width, height, hallway=False):
        '''
        Starts a circle from the firs position...
        '''
        start = self.blocks[0].position.point()
        center = start
        for i in range(int(width/5)):
            for j in range(int(height/5)):
                new_position = Position(start[0]+i,start[1]+j)
                new_block = Block(new_position)
                for block in self.blocks:
                    block.sync_borders_with(new_block)
                self.blocks.append(new_block)
                               
    def make_tpassage(self):
        '''
        Passage extending 10 ft., then T intersection extending 10 ft. to the right and left
        
        direction = random.randint(1,4)
        x = 1
        y = 1
        if direction == 1:
            x = -1
        if direction == 4:
            y = -1
        
        t_len = 2*random.randint(2,6)
        start = self.blocks[0].position.point()
        for i in range(random.randint(9,12)):
            for j in range(t_len):
                if i <= 1 or j == int(t_len/2) or j == int(t_len/2)-1:
                    if direction < 2:
                        new_position = Position(start[0]+(i*x),start[1]+(j*y))
                    else:    
                        new_position = Position(start[0]+(j*x),start[1]+(i*y))
                    new_block = Block(new_position)
                    for block in self.blocks:
                        block.sync_borders_with(new_block)
                    self.blocks.append(new_block)
        '''
        # AI can't draw these to save its life... so simplifying to a hallway
        self.make_rectangle(10,rand.randint(9,12)*5,hallway=True)
  
    def clear_room(self, clear_all = True):
        
        self.contents = 'Empty room'
        self.monster = ''
        self.traps = ''
        self.treasure = ''
        if clear_all:
            self.furnishings = []
            self.trick= ''
            self.hazards = ''
            self.state = ''
            self.color = 'gray'
        self.description = ''
        self.quest = ''
            
    def stock_room(self, hallway=False):
        '''
        '''
        CR = random.randint(1,3)+abs(int((self.parent.info['level'])))
        # Purpose, it's that little flame...
        if self.hallway:
            self.purpose = 'Hallway'
            self.color = 'white'
        elif self.stairs != None:
            self.purpose = 'Stairs'
            self.color = 'green'
            self.contents = ''
        elif self.is_exit == True:
            self.purpose = 'Exit (not a real room)'
            self.color = '#000000'
        else:
            try:
                self.purpose = self.parent.parent.roll_table(self.parent.parent.AppendixA['Purpose'][self.parent.info['purpose']])
            except KeyError:
                self.purpose = self.parent.parent.roll_table(self.parent.parent.AppendixA['Purpose']['General Dungeon Chambers'])
        self.state = self.parent.parent.roll_table(self.parent.parent.AppendixA['Current_Chamber_State'])

        if self.hallway == True or self.is_exit == True:
            self.contents = 'Empty room'
            self.color = 'gray'
        else:
            self.contents =  self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Chamber Contents'])
        
            if 'Monster' in self.contents:
                mon_type = self.contents.split(')')[0]+')'
                monlist = self.parent.info[mon_type].split('|')
                self.monster = random.sample(monlist,1)[0]
                if '[solo]' in self.monster:  # remove solo monsters once placed...
                    self.parent.info[mon_type].replace(self.monster,'').replace('| |','|').replace('||','|')
                self.monster = '{} [Monster Motivation: {}]'.format(self.monster, self.parent.parent.roll_table(self.parent.parent.AppendixA['Monster Motivation']))
                
                    
            if 'Hazard' in self.contents:
                self.hazards = self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Hazards'])
                self.furnishings.append('General Hazards: {}'.format(self.hazards))
            if 'Obstacle' in self.contents:
                self.hazards = self.hazards + '\n\n' + self.parent.parent.roll_table(self.parent.parent.AppendixA['Obstacles'])
                self.furnishings.append('General Obstacles: {}'.format(self.hazards))
            if 'Trap' in self.contents:
                self.traps = 'Trap({}):{} [Trigger: {}]\n'.format(self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Damage Severity'])
                                                         , self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Effects'])
                                                         , self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Trigger']))
            if 'Trick' in self.contents:
                tobj = self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Tricks']['Trick Objects'])
                self.traps = self.traps + 'Trick {}: {}'.format(tobj, self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Tricks']['Tricks']))
                self.furnishings.append('General Features: {}'.format(tobj))
                
            if 'treasure' in self.contents:
                
                if 'incidental' in self.contents:
                    hoard = False
                else:
                    hoard = True
                self.treasure = self.parent.parent.get_treasure(CR, hoard)
        
            n = int(len(self.blocks)**0.5)
            nmax = int(int(self.parent.info['Max Ceiling Height'].replace('ft',''))/5)
            nn = min(n,nmax)
            if nn > 2:
                self.ceiling_height = '{}ft'.format(random.randint(2,min(n,nmax))*5)
            else:
                self.ceiling_height = '10ft'
            for key in self.parent.parent.AppendixA['Dungeon Dressings'].keys():
                if key != 'Specific' and 'General' not in key:
                    self.furnishings.append('{}: {}'.format(key, self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Dressings'][key])))
                if 'general' in key.lower() and self.hallway == False and self.stairs == None:
                    for i in range(random.randint(2,len(self.doors)+2)):
                        self.furnishings.append('{}: {}'.format(key, self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Dressings'][key])))
                if key == 'Specific':
                    for skey in self.parent.parent.AppendixA['Dungeon Dressings'][key]:
                        for a in skey.split(' '):
                            if a.lower() in self.purpose.lower():
                                self.furnishings.append('{}: {}'.format('General Furnishings and Appointments ['+skey+']', self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Dressings'][key][skey])))
                                         
class Door():
    """
    A door.
    """
    
    def __init__(self, parent):
        self.parent = parent
        self.borders = []
        self.rooms = []
        d20 = random.randint(1,20)
        if d20 <= 10:
            self.door_type = 'Wooden'
        elif d20 == 11 or d20 == 12:
            self.door_type = 'Wooden, barred or locked'
        elif d20 == 13:
            self.door_type = 'Stone'
        elif d20 == 14:	
            self.door_type = 'Stone, barred or locked'
        elif d20 ==15:	
            self.door_type = 'Iron'
        elif d20 ==16:	
            self.door_type = 'Iron, barred or locked'
        elif d20 ==17:	
            self.door_type = 'Portcullis'
        elif d20 ==18:	
            self.door_type = 'Portcullis, locked in place'
        elif d20 ==19:	
            self.door_type = 'Secret door'
        elif d20 ==20:	
            self.door_type = 'Secret door, barred or locked'
        self.trapped = False
        self.traps = ''
        if self.trapped == True:
            self.traps = 'Trap({}):{} [Trigger: Opening the door]'.format(self.parent.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Damage Severity'])
                                                         , self.parent.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Effects']))
   
    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove the parent to prevent circular recursion during pickle
        self.rooms = []
        self.parent = None
        return self.__dict__.copy()
        
    def __setstate__(self, state):
        self.__dict__.update(state)
 
class Corridor():
    
    def __init__(self, start_border, stop_border, path):
        self.start_border = start_border
        self.stop_border = stop_border
        self.path = path

    def __getstate__(self):
        # Capture everything
        return self.__dict__.copy()
        
    def geometry_segments(self):
        points = [self.start_border.connection_point()]

        points.extend(position.move(0.5, 0.5).point() for position in self.path)

        points.append(self.stop_border.connection_point())

        return points

class Dungeon():
   
    def __init__(self, info=None, parent=None, stair_threshold=20):
        self.rooms = []
        self.corridors = []
        self.info = info
        self.parent = parent
        self.level = self.info['level']
        self.stair_threshold = stair_threshold
        
    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove the parent to prevent circular recursion during pickle
        if 'parent' in state:
            del state['parent']
        return self.__dict__.copy()
    
    def __setstate__(self, state):
        self.__dict__.update(state)
        # Manually restore the child's reference to this parent instance
        for room in self.rooms:
            room.parent = self

    def create_room(self, blocks, doors, trap=False, is_exit=False):
        room = Room(self, is_exit=is_exit)

        for i in range(blocks):
            room.expand()

        room.place_doors(doors, trap)
        
        if trap == True:
            room.clear_room()
            room.purpose = 'Door Trap'
            room.state ='empty save fro trap mechanism(s)'

        return room
        
    def create_rectangle_room(self, height, width, doors, stairs=None, hallway=False):
        room = Room(self, stairs=stairs, hallway=hallway)

        room.make_rectangle(height, width)

        room.place_doors(doors)

        return room

    def create_circle_room(self, diameter, doors):
        room = Room(self)

        room.make_circle(diameter)

        room.place_doors(doors)

        return room
        
    def create_tpassage(self, doors):
        room = Room(self, hallway=True)

        room.make_tpassage()

        room.place_doors(doors, t_pass=True)
        
        return room
       
    def door_borders(self):
        for room in self.rooms:
            for border in room.door_borders():
                if not border.used:
                    yield border
  
    def draw_dungeon(self,show=True):
        plt.axes().set_aspect('equal', 'datalim')
        
        fig = plt.figure(1)
        
        for room in self.rooms:
            borders = list(room.geometry_borders())
            plt.fill(*zip(*make_contour(borders)), '#ffffff')
            plt.fill(*zip(*make_contour(borders)), room.color, alpha=0.25)
        
            for border in borders:
                plt.plot(*zip(*border), color=room.color, linewidth=3, alpha=1.0)
        
            for border in room.grid_borders():
                plt.plot(*zip(*border), color=room.color, linewidth=1, alpha=0.5)
            
            # room labels...
            xset = set()              
            yset = set()
            for lst in borders:
                for tup in lst:
                    xset.add(tup[0])
                    yset.add(tup[1])
            x = (max(xset)+min(xset))/2
            y = (max(yset)+min(yset))/2
            plt.text(x, y, f"[{room.room_id}]", fontsize=8)
        
        for room in self.rooms:
            for door_border in room.door_borders():
                plt.plot(*zip(*door_border.geometry_borders()), color='b', linewidth=6, alpha=0.75)
            
        for corridor in self.corridors:
            plt.plot(*zip(*corridor.geometry_segments()), color='#000000', linewidth=1, alpha=1)

        plt.savefig(self.parent.file_path("Maps/{} level {}.png".format(self.parent.filename, self.info['level'])), dpi=300, bbox_inches='tight')
        if show == True:
            plt.show()
    
    def map_dungeon(self,show=True, explored=False, objects=None, color='blue', secret_doors=False, paper='#D7D0C2'):
        '''
        This is a map of the dungeon, if players want to have their characters be good at this,
        or denezins offer to make a map for the players.
        '''
        with plt.xkcd():
            plt.clf()
            fig = plt.figure(1)
            plt.axes().set_aspect('equal', 'datalim')
            fig.set_facecolor(paper)
        
            rooms = self.rooms
            if explored == True:
                rooms = [room for room in rooms if room.color=='green' or room.description != '']
            if objects != None:
                rooms = [room for room in rooms if room in objects]

            if len(rooms) > 0:
                for room in rooms:
                    borders = list(room.geometry_borders())
                    #plt.fill(*zip(*make_contour(borders)), '#ffffff')
        
                    # room lines only
                    for border in borders:
                        plt.plot(*zip(*border), color=color, linewidth=3, alpha=1.0)
        
                    # stairs...
                    if 'stair' in room.purpose.lower():
                        block_pos = list(set([block.position.point() for block in room.blocks]))
                        x = sum([a[0] for a in block_pos])/len(block_pos)
                        y = sum([a[1] for a in block_pos])/len(block_pos) + 0.5
                        if 'down' in room.purpose.lower():
                            L = r'$\downarrow$'
                        else:
                            L = r'$\uparrow$'
                        y2 = y - 0.5
                        y1 = y + 0.5    
                        plt.hlines(y, xmin=x, xmax=x+1, linewidth=3, color=color)
                        plt.hlines(y1, xmin=x-0.25, xmax=x+1.25, linewidth=3, color = color)
                        plt.hlines(y2, xmin=x+0.25, xmax=x+0.75, linewidth=3, color = color)
                        plt.text(x+0.5, y, L, ha='center', va='center', color=color, zorder=21, fontsize=20)
                
                '''
                for room in self.rooms:
                    for door_border in room.door_borders():
                        plt.plot(*zip(*door_border.geometry_borders()), color='b', linewidth=6, alpha=0.75)
                '''    
        
                lines = []
                # non-secret doors
                for room in rooms:
                    for door in room.doors:
                        if 'secret' not in door.door_type.lower():
                            for door_border in door.borders:
                                if door_border.position.point() in [block.position.point() for block in room.blocks]:
                                    plt.plot(*zip(*door_border.geometry_borders()), color=color, linewidth=12, alpha=1)
                                    lines.append(door_border)
        
                # secret doors
                if secret_doors == True or objects != None:
                    for room in rooms:
                        for door in room.doors:
                            if 'secret' in door.door_type.lower():
                                if objects == None or door in objects:
                                    for door_border in door.borders:
                                        if door_border.position.point() in [block.position.point() for block in room.blocks]:
                                            # plt.plot(*zip(*door_border.geometry_borders()), color=color, linewidth=12, alpha=0.5, linestyle='--')
                                            nlst = door_border.geometry_borders()
                                            x = sum([a[0] for a in nlst])/2
                                            y = sum([a[1] for a in nlst])/2
                                            plt.text(x, y, 'S', ha='center', va='center', color=color, zorder=21)
                                            lines.append(door_border)
        
                for corridor in [corridor for corridor in self.corridors if 
                                 corridor.start_border in lines and 
                                 corridor.stop_border in lines]:
                    plt.plot(*zip(*corridor.geometry_segments()), color=color, linewidth=1, alpha=1)
        
                
                plt.axis('off')
                plt.savefig(self.parent.file_path("map_level_{}.png".format(self.info['level'])), dpi=300, bbox_inches='tight')
                
                if show == True:
                    plt.show()
                plt.clf()
                return self.parent.file_path("map_level_{}.png".format(self.info['level']))
            else:
                plt.clf()
                return None
            
    def is_intersect_room(self, room):
        return any(current_room.is_intersect(room) for current_room in self.rooms)

    def room_positions_bruteforce(self, max_intersection_radius, new_room, dungeon_positions):
        
        filled_cells = {position.point() for position in dungeon_positions}


        for max_distance in range(0, max_intersection_radius):
            #for dungeon_door in self.door_borders():
            for i, dungeon_door_object in enumerate(self.get_free_doors()):            
                dungeon_door = dungeon_door_object.borders[0]
                max_distance, dungeon_door, new_room_door, x, y = self.room_position_from_door(max_distance, new_room, dungeon_positions, dungeon_door)
                if max_distance != -1:
                    yield (max_distance, dungeon_door, new_room_door, x, y)
               
    def room_position_from_door(self, max_intersection_radius, new_room, dungeon_positions, dungeon_door):
        '''
        dungeon_door = a door border, not a door object
        '''
        filled_cells = {position.point() for position in dungeon_positions}
        if max_intersection_radius == None:
            max_intersection_radius = 1
        for new_room_door in new_room.door_borders():
            for x, y in points_at_circle(*dungeon_door.position.point(), radius=max_intersection_radius):

                for _ in range(4):
                    new_room.rotate_clockwise()
                    new_room.move(x - new_room_door.mirror().position.x,
                                  y - new_room_door.mirror().position.y)
                    

                    check_position = new_room_door.position.point()[0] == dungeon_door.position.point()[0] or new_room_door.position.point()[1] == dungeon_door.position.point()[1]
                   
                    if dungeon_door.is_mirrored(new_room_door) and check_position and not self.check_blocks(new_room):
                        return (max_intersection_radius, dungeon_door, new_room_door, x, y)
                        
        return (-1, None, None, None, None)

    def check_blocks(self, new_room):
        '''
        checks if new_room overlaps any used blocks in the dungeon
        '''
        check_blocks = False
        for block in new_room.blocks:
            for room in self.rooms:
                for dblock in room.blocks:
                    if block.position.point() == dblock.position.point():
                        check_blocks = True
        return check_blocks
                                    
    def block_positions(self):
        positions = set()

        for room in self.rooms:
            positions |= room.block_positions()
            
        return positions
                
    def expand(self, new_room, max_intersection_radius=1, current_door=None, stairway=False):
        '''
        Finds a place for a room in the dungeon
        '''
        threshold = 1  #set for room extra connections
        
        if len(self.rooms) == 0 or stairway:
            self.rooms.append(new_room)
            return True

        elif self.check_free_doors() > 0:
            dungeon_positions = self.block_positions()
            
            corridor_path = None
            dungeon_door = None

            # ATTENTION: method room_positions_bruteforce make modifications of new_room
            #            it is not very good decission
            
            for door in self.get_free_doors():
                dungeon_door = door.borders[0]
                max_distance, dungeon_door, new_room_door, x, y = self.room_position_from_door(max_intersection_radius,
                                                                                                      new_room,
                                                                                                      dungeon_positions,
                                                                                                      dungeon_door)
                if dungeon_door is not None:                                                                            
                    dungeon_door_out_position = dungeon_door.mirror().position
                    new_room_door_out_position = new_room_door.mirror().position

                    filled_positions = dungeon_positions | new_room.block_positions()

                    path_length, corridor_path = find_path(dungeon_door_out_position,
                                                           new_room_door_out_position,
                                                           filled_cells=filled_positions,
                                                           max_path_length=max_distance)

                    if path_length is None:
                        return False

                    # door is free and the positions are opposed      
                   
                    if len(dungeon_door.door.borders) < 2 and dungeon_door.is_mirrored(new_room_door) and len(new_room_door.door.borders) < 2:
                        # we're good...
                        door = dungeon_door.door
                        new_room.doors.pop(new_room.doors.index(new_room_door.door))
                        door.borders.append(new_room_door)
                        door.rooms.append(new_room)
                        self.rooms.append(new_room)
                        new_room.doors.append(door)

                        new_corridor = Corridor(dungeon_door, new_room_door, corridor_path)

                        self.corridors.append(new_corridor)
                        
                     
                            
                       
                                
                        return True
                    elif new_room.blocks == 1:  #if a 1-square room fails, the door is cursed
                        self.remove_door(door)
           
        return False
       
    def starting_room(self):
        """

        """
        d10 = random.randint(1,10)   
        
        # 1	Square, 20 × 20 ft.; passage on each wall
        if d10 == 1:
            new_room = self.create_rectangle_room(20,20,4)
        # 2	Square, 20 × 20 ft.; door on two walls, passage in third wall
        elif d10 == 2:
            new_room = self.create_rectangle_room(20,20,3)
        # 3	Square, 40 × 40 ft.; doors on three walls
        elif d10 == 3:
            new_room = self.create_rectangle_room(40,40,3)
        # 4	Rectangle, 80 × 20 ft., with row of pillars down the middle; two passages leading from each long wall, doors on each short wall
        elif d10 == 4:
            if random.randint(1,2)==1:
                new_room = self.create_rectangle_room(80,20,4)
            else:
                new_room = self.create_rectangle_room(20,80,4)
        # 5	Rectangle, 20 × 40 ft.; passage on each wall
        elif d10 == 5:
            new_room = self.create_rectangle_room(20,40,4)
        # 6	Circle, 40 ft. diameter; one passage at each cardinal direction
        # 7	Circle, 40 ft. diameter; one passage in each cardinal direction; well in middle of room (might lead down to lower level)
        elif d10 == 6 or d10 == 7:
            new_room = self.create_circle_room(40,4)
        # 8	Square, 20 × 20 ft.; door on two walls, passage on third wall, secret door on fourth wall
        elif d10 == 8:
            new_room = self.create_rectangle_room(20,20,4)
        # 9	Passage, 10 ft. wide; T intersection
        elif d10 == 9:
            new_room = self.create_tpassage(3)
        # 10	Passage, 10 ft. wide; four-way intersection
        elif d10 == 10:
            new_room = self.create_tpassage(4)
         
        self.expand(new_room)
        check = False
        while check == False:
            check = self.expand(self.create_room(0,1,is_exit=True))
                  
    def check_level(self, new):
        '''
        '''
        nlevel = int(self.info['level']) + new
        try:
            a = self.parent.levels[nlevel]
            return nlevel, True
        except:
            return nlevel, False
    
    def check_free_doors(self):
        '''
        '''
        free_doors = 0
        for room in self.rooms:
            for door in room.doors:
                if len(door.borders) == 1:
                    free_doors += 1
        return free_doors
    
    def get_free_doors(self):
        doors = []
        for room in self.rooms:
            for door in room.doors:
                if len(door.borders) == 1:
                    doors.append(door)
        ret_doors = []
        # a set changes the order...
        [ret_doors.append(door) for door in doors if door not in ret_doors]
        return ret_doors
    
    def remove_door(self, door):
        #corridor removal...
        for cor in [corridor for corridor in self.corridors if corridor.start_border in door.borders and corridor.stop_border in door.borders]:
            # self.corridors.pop(self.corridors.index(cor))
            self.corridors = [a for a in self.corridors if a != cor]
            del cor
        # clear borders
        for border in door.borders:
            border.used = False
            border.can_has_door = False
            border.door = None
        for room in door.rooms:
            room.doors = [a for a in room.doors if a is not door]
        del door
    
    def connect_free_doors(self, threshold):
        # Connect to doors near rooms...
        doors = self.get_free_doors()
        for door in doors.copy():
            if door in doors:  #we are removing doors we find
                find_direction = door.borders[0].mirror().direction
                dborder = door.borders[0]
                droom = door.rooms[0]
                # check the doors
                tborder = None
                nroom = None
                mthreshold = threshold + 0.0001
                for ndoor in doors:
                    if ndoor is not door and len(ndoor.borders) == 1 and ndoor.borders[0].direction == find_direction:
                        if get_distance(door.borders[0].position.point(), ndoor.borders[0].position.point()) <= mthreshold:
                            mthreshold = get_distance(door.borders[0].position.point(), ndoor.borders[0].position.point()) # make sure none are better
                            tborder = ndoor.borders[0]
                            nroom = ndoor.parent
                            # remove door from parent and list
                            self.remove_door(ndoor)
                if tborder is None:  #check hallways
                    for room in [room for room in self.rooms]:
                        for border in [border for border in room.borders() if border.direction == find_direction and border.internal == False]:
                            if dborder not in [a for a in room.borders()] and get_distance(dborder.position.point(), border.position.point()) <= mthreshold:
                                mthreshold = get_distance(dborder.position.point(), border.position.point())
                                tborder = border
                                nroom = room
                if tborder is not None:
                    # we have a connection...
                    door.borders.append(tborder)
                    tborder.can_has_door = True
                    nroom.doors.append(door)
                    door.rooms.append(nroom)
                    doors = [a for a in doors if a != door]
                    corridor_path = simple_path(door.borders[0].position.point(),
                                                door.borders[1].position.point())
                    self.corridors.append(Corridor(door.borders[0], door.borders[1], corridor_path))
    
    def add_area(self):
        '''
        Rolls on some tables from the DMG
        '''
        stairs = False
        down_prior = False
        room_added = False
        free_doors = self.check_free_doors()
        tries = 0
        if free_doors >= 1:
            # 1% for every 10 rooms - 3% for every exit...  
            exit_chance = 100 - int(len(self.rooms)/10) + 3*sum([room.is_exit for room in self.rooms])
            if random.randint(1,100) >= exit_chance:
                ## EXIT
                new_room = self.create_room(0,1,is_exit=True)
            else:
                d20 = random.randint(1,20)
                # make sure we have some stairs...
                if len(self.rooms) >= self.stair_threshold:
                    nlevel, check = self.check_level(-1)
                    stairs_down = len([room for room in self.rooms if 'stairwell' in room.purpose.lower() and 'down' in room.purpose.lower()])
                    if stairs_down == 0 and check == True:
                        d20 = 19  #we need some stairs..
                        down_prior = True
                if d20 <= 2:
                    # Passage extending 10 ft., then T intersection extending 10 ft. to the right and left
                    new_room = self.create_tpassage(3)
                elif d20 > 2 and d20 <= 8:
                    # Passage 20 ft. straight ahead
                    new_room = self.create_rectangle_room(10*random.randint(4,10),10,random.randint(3,4))
                elif d20 >= 9 and d20 <= 18:
                    # Chamber
                    nd20 = random.randint(1,20)
                    ndoors = random.randint(1,4)
                    if nd20 <= 2:	
                        #Square, 20 × 20 ft.1
                        new_room = self.create_rectangle_room(20,20,1+ndoors)
                    elif nd20 == 3 or nd20 == 4:
                        # Square, 30 × 30 ft.1
                        new_room = self.create_rectangle_room(30,30,1+ndoors)
                    elif nd20 == 5 or nd20 == 6:
                        # Square, 40 × 40 ft.1
                        new_room = self.create_rectangle_room(40,40,1+ndoors)
                    elif nd20 >= 7 and nd20 <= 9:
                        #	Rectangle, 20 × 30 ft.1
                        new_room = self.create_rectangle_room(20,30,1+ndoors)
                    elif nd20 >= 10 or nd20 <= 12:
                        #	Rectangle, 30 × 40 ft.1
                        new_room = self.create_rectangle_room(30,40,1+ndoors)
                    elif nd20 == 13 or nd20 == 14:
                        #	Rectangle, 40 × 50 ft.2
                        new_room = self.create_rectangle_room(40,50,2+ndoors)
                    elif nd20 == 15:
                        #	Rectangle, 50 × 80 ft.2
                        new_room = self.create_rectangle_room(50,80,1+ndoors)
                    elif nd20 == 16:
                        #	Circle, 30 ft. diameter1
                        new_room = self.create_circle_room(30,1+ndoors)
                    elif nd20 == 17:
                        #	Circle, 50 ft. diameter2
                        new_room = self.create_circle_room(50,2+ndoors)
                    elif nd20 == 18:
                        #   Octagon, 40 × 40 ft.2
                        new_room = self.create_circle_room(40,2+ndoors)
                    elif nd20 == 19:
                        #	Octagon, 60 × 60 ft.2
                        new_room = self.create_circle_room(60,2+ndoors)
                    elif nd20 == 20:
                        #	Trapezoid, roughly 40 × 60 ft.2
                        new_room = self.create_rectangle_room(40,60,1+ndoors)      
              
                #### THIS IS A THING THAT NEEDS WORK ####
                elif d20 == 19:
                    # Stairs
                    stairs = True
                    
                elif d20 == 20:
                    #False door with trap
                    new_room = self.create_room(0,1,trap=True)
                    
            #last bit...
            
            if not stairs:
                room_added = self.expand(new_room)
            else:
                stairs = True
            if stairs == True:
                # stair code...
                new_levels = []
                room_added = False
                new_room = self.create_rectangle_room(10,10,1)
                nd20 = random.randint(1,20)
                up = True
                if nd20 <= 12 or nd20 == 16 or nd20 == 18 or down_prior == True:
                    # Down one level to a chamber
                    nlevel, check = self.check_level(-1)
                    up = False
                elif nd20 >= 13 and nd20 <= 15 or nd20 == 17 or nd20 >= 19:
                    #	Up one level to a chamber
                    nlevel, check = self.check_level(1)
                if check:
                    mirror_room = Room(self, stairs=new_room)
                    mirror_room.blocks = []
                    check = self.expand(new_room)
                    if check == True:
                        # add the blocks
                        for block in new_room.blocks:
                            x, y = block.position.point()
                            new_block = Block(Position(x, y)) 
                            for nblock in mirror_room.blocks:
                                nblock.sync_borders_with(new_block)
                            mirror_room.blocks.append(new_block)
                            mirror_room.color = new_room.color
                        if up:
                            up_down = [new_room, mirror_room]
                        else:
                            up_down = [mirror_room, new_room]
                            
                        up_down[0].purpose = 'Stairwell Up'
                        up_down[1].purpose = 'Stairwell Shaft Leading Down'
                        up_down[0].state = 'Stairs Leading Up From a Door'
                        up_down[1].state = 'stairs filling the square from edge to edge'
                        upstr = '''
General: GRANITE STAIRS FROM ROOM.png
1. MASK BOUNDARIES STRICT
The floor is ONLY for the area defined by the floor mask in mask.png. Do NOT extend floor textures onto the white wall areas. MASK IS A HARD CLIPPING PATH. The black pixels in MASK.png are a physical void.
2. STAIR HEIGHT VS WALLS
The stairs are physical stone blocks that are attached to the vertical walls. The walls represented by white areas must look like 90-degree upright surfaces rather than flat floor. 
3. DOOR MASK PRIORITY
The door must be rendered flush against the floor at the doorway mask location. No stair wedges can overlap or exist inside the door's physical space. The DOOR must remain inside the door gap and flush with the vertical wall as a flat vertical plane.
4. HEIGHT MAP DEPTH
The grayscale in room.png is a Z-axis height map. Pure White is the highest point at 10ft elevation. Dark Grey is the lowest point at 0ft elevation. Each wedge is a discrete solid slab. Render a deep shadow on the clockwise edge of every black line to show the 3D step down.
5. NO TEXTURE BLEED
The floor texture must stop at the first step. The stairs themselves are clean worn rough-hewn granite.  DO NOT ADD FLOOR TEXTURE TO STAIRS
6. FISH EYE
Walls MUST REMAIN IN THEIR GRAY TRAPEZOIDS to allow the stairs to appear to be rising toward the camera.
'''
                        up_down[0].furnishings.append(upstr)
                        up_down[1].furnishings.append('''
General: Spiral Stairs DESCENDING from a landing

### THE STAIRS (GRAY WEDGES)
- Each wedge is a free slab of granite. 
- The color of the stairs in room.png is a height map, each stair is 6 inches lower than the next stair as they get darker
- The stair shapes in room.png are geometric truth
- Wall gfaces aare shring wrapped to the outer stair edges

### THE WALLS (BLUE PIXELS)
- The four verticalwalls are NOT 90 degrees; they are SLANTED INWARD.
- All four walls must converge toward a single central point at the bottom of the shaft.
- This creates the internal geometry of an inverted square-based cone.
- All blue pixels are the slanting wall faces

### CENTER PILLAR
- The black circle in the center is a granite pillar running all the way down the shaft.
- Stairs come oput from this pillar and extand to the walls.

### HARD MASK RULE
- No white pixel in mask.png that is blue in room.png may be anything other than an inner wall face.
- THE PIT IS FILLED WITH STAIRS, THE BOTTOM IS UNSEEN (as there are more flights below the visible)
- Black lines in mask.png mark hard barriers between textures, the square is the landing, the area the door, the X the edges of the walls, the circle the pillar.

### VISUAL RULE:
- The wall texture must directly touch the stair edges and the door edges. 
- there is no other horizontal surfaces aside from the white square and the gray polygon stairs.

### DATA OVERRIDE THE INVISIBLE VERTEX
- The black "X" in the map is a NON-RENDERING COORDINATE. It represents the mathematical CORNER where the vertical walls meet. 
- PROHIBIT the AI from drawing any black lines, ink, or "X" shapes in the final render. 
''')
                        mirror_room.place_doors(1)
                        mirror_room.parent = self.parent.levels[nlevel]
                        mirror_room.clear_room(True)
                        room_added = self.parent.levels[nlevel].expand(mirror_room, stairway=True)
                        
                        
                        if room_added == False:
                            self.rooms.pop(new_room)
                        else:
                            new_room.stairs = mirror_room
                
            # connect loose doors
            self.connect_free_doors(threshold=1)
            
            