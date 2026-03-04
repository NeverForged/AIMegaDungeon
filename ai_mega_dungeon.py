import os
import io
import cv2
import json
import enum
import heapq
import shutil
import pickle
import base64
import openai
import random
import requests
import warnings
import collections
import numpy as np
import pandas as pd
import random as rand
from PIL import Image
from scipy import ndimage
import matplotlib.image as img
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import matplotlib.patches as patches
from matplotlib.patches import Polygon
from matplotlib.offsetbox import OffsetImage, AnnotationBbox


from IPython.display import display, Image as IPImage

class AIMegaDungeon:
    _slots_ = ('levels', 'game')
    
    def __init__(self, filename='Test', levelfile='levels.csv', keys='|', game='D&D 5E 2024'):
        '''
      

        levels -> a dict of dungeon objects, each representing a level of the dungeon.

        level_info -> level information, key is z coordinate (0 for first level)

        self.doors -> door information, 
        
        keys = OPENAI API KEY|OPENROUTER API KEY
        '''
        self.OPENAI_API_KEY = keys.split('|')[0]
        self.OPENROUTER_API_KEY = keys.split('|')[1]
        # Get the directory of the class
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.filename = filename  
        self.game = game
        
        try:
            self.levels = self.load(filename)
      
            self.levelsdf = pd.read_csv(self.file_path(levelfile), sep='\t')
            new = 1
        except: # need a new instance
            print('New Dungeon...')
            self.levelsdf = pd.read_csv(self.file_path(levelfile), sep='\t')
            self.levels = {}
            
            with open(self.file_path('AppendixA.pickle'), 'rb') as file:   
                self.AppendixA = pickle.load(file)
            print('Dungeon {} Created'.format(filename))
            
        self.char_level_ave = 1

    ## ADMIN FUNCTIONS
    def file_path(self, filename):
        return os.path.join(self.current_dir, '{}'.format(filename))
        
    def load(self, filename=None):
        with open(self.file_path(filename+'.aad'), 'rb') as file:    
                levels = pickle.load(file)
        return levels
    
    def save(self, filename='QuickSave'):

        with open(self.file_path(filename+'.aad'), 'wb') as file:
            pickle.dump(self.levels, file)  
      
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
                    prompt = 'Write a {} Encounter: Create a Medium CR {} encounter based around {}\n'.format(self.game, CR, room.monster)
                    prompt = prompt + '    - Be sure to include a basic outline of combat strategy, as if you were the author of "The Monsters Know What They Are Doing", for the first 3 rounds of combat, including surrender conditions/motivations\n'
                    prompt = prompt + '    - Inclue any note on roleplay for the creatures.\n'
                    propmt = propmt + "    - Include the numbers of creatures, and adjust fro 4-6 characters"
                    prompt = prompt + '''    - Add an Esculation Clock appropriate to the room and encounter 
                    [Esculation Clocks track hazards (volcano eruptions, crumbling floors), NPC actions (guards arriving), or environmental changes (tide changes, magic fading)
                    The Escalation Clock Pattern
                        Duration: Set a countdown of 1d4+1 rounds (literally write 1d4+1...)
                        The Telegraph (The "Tell"): Describe a sensory warning that intensifies each round (e.g., a sound, a visual crack, a rising temperature).
                        The Payload (The "Snap"): Define a significant mechanical shift that occurs when the clock hits zero. It must either damage the players, block an path, or add new threats. It should change the "win condition" of the room.]\n
                    '''
                    prompt = prompt + '\n\nInclude the CR, HP, AC, and lookup information (book, pg number) for each monster\n\n'
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
            room_desc_basic = room_desc_basic + f"\nCeiling: {room.parent.info['ceilings']}"
            room_desc_basic = room_desc_basic + f"\nWall: {room.parent.info['walls']}"
            room.description = room_desc_basic                                       
        return room.description   
   
    ## AI CALLS & TOOLS
    def get_chat_response(self, prompt, role="You are a helpful assistant.", model="gpt-3.5-turbo"):
        client = openai.OpenAI(api_key=self.OPENAI_API_KEY) # Create an OpenAI client instance
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
         
    def draw_room(self, room, show=True):
        '''
        Creates a mask and base image for AI to draw the room from
        '''
        
        inner_radius = 0.25  #in case of stairs
        Diagonals = make_diagonals(room)
        fakeroom = make_fakeroom(room)
        borders = list(room.geometry_borders())
        wallborders = list(fakeroom.geometry_borders())
        figsize, (xmin, xmax), (ymin, ymax) = get_figsize_from_wallborders(wallborders, dpi=70, pixels_per_unit=70, padding_units=0)
        fig = plt.figure(figsize=figsize, dpi=70)
        fig.set_facecolor('black')
        plt.axes().set_aspect('equal', 'datalim')
        plt.axis('off')
        # mask the area white...
        plt.fill(*zip(*make_contour(wallborders)), '#ffffff', alpha=1)
        #plt.fill(*zip(*make_contour(borders)), '#ffffff')
        #plt.fill(*zip(*make_contour(borders)), 'g', alpha=0.5)

       
        # draw the walls...
        inner_wall_border_line = []
        if 'stairwell' in room.purpose.lower() and 'down' in room.purpose.lower():
            nborders = list(room.door_geometry_borders())
            plt.fill(*zip(*make_contour(nborders)), '#ffffff')
            for border in nborders:
                inner_wall_border_line.append(plt.plot(*zip(*border), color='k', linewidth=2, alpha=1))
        else:
            for border in borders:
                inner_wall_border_line.append(plt.plot(*zip(*border), color='k', linewidth=2, alpha=1))
        for border in wallborders:
             inner_wall_border_line.append(plt.plot(*zip(*border), color='k', linewidth=25, alpha=1.0))

        
        for coords in Diagonals:
            x = [coord[0] for coord in coords]
            y = [coord[1] for coord in coords]
            inner_wall_border_line.append(plt.plot(x, y, color='k',linewidth=2, alpha=1.0))
        if 'stairwell' in room.purpose.lower() and 'down' in room.purpose.lower():
            ax = plt.gca()
            x_lims = ax.get_xlim()
            y_lims = ax.get_ylim()
            inner_wall_border_line.append(ax.plot([x_lims[0], x_lims[1]], [y_lims[1], y_lims[0]], 
                                            color='black', linewidth=2, zorder=10))
            inner_wall_border_line.append(ax.plot([x_lims[0], x_lims[1]], [y_lims[0], y_lims[1]], 
                                            color='black', linewidth=2, zorder=10))
            
                
        # add gridlines
        for border in room.grid_borders():
            plt.plot(*zip(*border), color='k', linewidth=1, alpha=0.5)

        # blue lines for doors
        for i, door in enumerate(room.doors):
            ddx, ddy = 0, 0 
            if 'Portcullis' in door.door_type:
                ddx, ddy = .2, .2
            border = door.borders[door.rooms.index(room)]
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
                plt.plot(xlst,ylst,color='k', linewidth=2, alpha=1)

        # add central pillar for stairwell
        if 'stairwell' in room.purpose.lower():
            # Get the room center and bounds
            ax = plt.gca()
            xmin, xmax = ax.get_xlim()
            ymin, ymax = ax.get_ylim()
            center_x, center_y = (xmin + xmax) / 2, (ymin + ymax) / 2
            # Add pillar to the mask...
            pillar = plt.Circle((center_x, center_y), inner_radius, color='k', zorder=5)
            ax.add_patch(pillar)
            # blue lines for doors

        # Save the MASK
        plt.savefig(self.file_path('mask.png'), transparent=False, facecolor='white', bbox_inches=None, dpi=70) 

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
                # Ensure it clips to the trapezoid walls
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
            border = door.borders[door.rooms.index(room)]
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
    
    def render_room(self, room, show=True):
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
            border = door.borders[door.rooms.index(room)]
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
        
        newline = ''
        for tup in [(ud, 'NORTHERN', ut), (dd, 'SOUTHERN', dt), (ld, 'WESTERN', lt), (rd, 'EASTERN', rt)]:
            if tup[0] == False:
                newline = newline + '    THE {} WALL IS SOLID. THERE ARE NO DOORS/WINDOWS/OPENINGS IN THE {} WALL.  The AI must strictly ignore any instinct to add "balance" or "symmetry" to the room. The {} boundary is a dead-end.\n'.format(tup[1], tup[1], tup[1])

        floorline =  '''    FLOORS: The black grid is strictly for the horizontal floor. Do not project or continue any grid lines into the blue trapezoids. The floor texture and grid must stop abruptly—with zero transition—at the inner black line. If a grid line hits the black boundary, it must disappear instantly.
                            Floor is only in the gridded section, and must not creep into the wall area (no floor in in the blue trapezoids from room.png).\n"
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
            f"IMAGE EDITING TASK: Cinematic Schematic Render.\n\n"
            f"STRICT MASK RULE: Use MASK.png as a physical stencil. \n"
            f"SAFETY OVERRIDE: The black pixels in MASK.png are a hard boundary." # If a pixel is black in the mask, do not render any light, shadow, or texture there. Keep it pure black."
            f"    The thick black lines are the 'clipping edge.' If a pixel is outside that central area, it MUST be the vertical wall material, never the floor material."
            #f"- BLACK pixels in MASK.png are FROZEN. Do not change them.\n"
            # f"- WHITE pixels in MASK.png are the ONLY editable zones. \n\n"
            f"1. ARCHITECTURE: The blue trapezoids are VERTICAL WALLS that act as a 3D cookie-cutter. They physically overlap and HIDE the floor. There is no grid on the walls. The floor does not 'meet' the wall; it is simply cut off by the wall. Do not render any bevel, shadow-line, or ledge where the floor hits the blue area\n."
            f"    ARCHITECTURE: The BLUE trapezoids represent SOLID, IMPENETRABLE WALLS. If a wall does not have a brown door polygon, it is a single, continuous, and unbroken wall.\n"
            #f"2. MOOD & STYLE: {room.purpose} ({room.state})  Use Even neutral lighting (No directional shadows separating objects) and realistic textures.\n"
            f"2. MOOD & STYLE: {room.purpose} ({room.state})  Use cinematic lighting and realistic textures.\n"
            f"{floorline}"
            f"        Texture: {room.parent.info['floors']}."  
            f"         -Treat the black boundary line as a physical barrier. THIS Texture must be 'clipped' by the wall mask. Do not anti-alias or blend this area into the wall.\n"
            f"    WALLS (BLUE in ROOM.png): Vertical inner wall faces\n"
            f"        Texture: {room.parent.info['walls']}. Thicker black line is top of wall.\n"
            f"        These are physically separate from the floor. Even if the textures are identical, the wall grain must be vertical and the floor grain must be horizontal. The wall texture MUST NOT touch the floor grid."
            f"    Walls should start at the black line around the gridded section.\n"
            f"3. DOOR ANCHORS: ONLY render doors where you see a BROWN POLYGON and a RED LABEL. If an area is BLUE, it is a SOLID WALL\n"
            f"    Render a closed medieval door made of the labeled material exactly inside those gaps. If a wall is solid black in the mask, it is a PERMANENT wall.\n"
            f"    The Brown trapezoids are gaps in the walls filled with a door.  Doors must be INSIDE the walls like real doors\n"
            f"    Remove the red labels\n"
            f"{newline}"
            f"    Do not add 'cinematic' door frames or gaps where they are not drawn in room.png."
            f"4. DETAILS: {furnishing_list} \n"
            f"   - MANDATORY SIZE: Scale items accordingly to one grid square being 5ft.\n"
            f"   - VIEW: Strict 90-degree TOP-DOWN. Objects must look like flat floor-details, not 3D models.\n"
            f"5. NO EXTRA OPENINGS: The layout is a closed system.\nNo extra gridlines.  Do not make up your own gridlines.\n"
            f"   NO DOORS ON THE FLOOR, NOTHING OUTSIDE THE WALLS, NO EXTRA DOORS THAT ARE NOT IN THE MASK\n"
            f"   USE REALISTIC TEXTURES\n"
            f" DO NOT DRAW BLACK LINES FROM mask.png on the final image, especially wall corner lines\n"
            f"      only lines from room.png are to be reprooduced on final image\n"
            f"OUTPUT: ONLY the base64 data URI. No text."
        )
        

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
                if show == True:
                    display(IPImage(filename=output_image_path))
            else:
                print("⚠️ No image returned — model may have replied with text only.")
        else:
            print("❌ API Error", response.status_code, response.text)
    
    """
   
        
  
        
    d
            
    def build_battlemap_prompt(self,
        canvas_w,
        canvas_h,
        floor_w,
        floor_h,
        grid_px,
        room_shape,
        room_theme,
        floor_material,
        wall_material,
        doors,
        contents=None,
        art_theme="Dragon Entwined With Celtic Knotworks",
        units="ft",
        debug=False
        ):
    

        wall_spaces_ft = 10

        
        dir_dct = {'south':'bottom','north':'top','east':'right side','west':'left side'}
        doors_text = "\n"
        dct_door_stuff = {'north':floor_h, 'south':floor_h, 'east': floor_w, 'west':floor_w}
        floor_ratio = self.get_image_ratio([floor_w, floor_h])
        floor_height = int(floor_h/5)
        floor_width = int(floor_w/5)
        if doors:
            doors_text_lst = []
            for i, d in enumerate(doors):
                '''
               Create doors
                '''
                fraction = d['placement'][0]/d['placement'][1]
                if d['wall'] in ['north', 'south']:
                    door_center_x = floor_width * fraction
                    door_x_start = round(door_center_x - d['width_ft']/10,2)
                    door_x_end   = round(door_center_x + d['width_ft']/10,2)
                    y = 0 if d['wall'] == 'south' else floor_height
                    doors_text_lst.append('\t{}. {} wall — {}, {} feet wide, door spans x={} to x={}, y={})'.format(i+1
                                                                                                                   , d['wall']
                                                                                                                   , d['type']
                                                                                                                   , d['width_ft']
                                                                                                                   , door_x_start
                                                                                                                   , door_x_end
                                                                                                                   , y))
                elif d['wall'] in ['west', 'east']:
                    door_center_y = floor_height * fraction
                    door_y_start = round(door_center_y - d['width_ft']/10,2)
                    door_y_end   = round(door_center_y + d['width_ft']/10,2)
                    x = 0 if d['wall'] == 'west' else floor_width        
                    doors_text_lst.append('\t{}. {} wall — {}, {} feet wide, door spans y={} to y={}, x={})'.format(i+1
                                                                                                                   , d['wall']
                                                                                                                   , d['type']
                                                                                                                   , d['width_ft']
                                                                                                                   , door_y_start
                                                                                                                   , door_y_end
                                                                                                                   , x))
            doors_text = '\n'.join(doors_text_lst)
        # Prepare contents text
        contents_text = "None"
        if contents:
            contents_text = "\n".join([f"- {c}" for c in contents if len(c.split(':')[1]) > 0])

        
        squares = (max(floor_w, floor_h)+wall_spaces_ft)/5
        square_to_px = 1024/squares

        feet = squares*5
        px_per_foot = int(1024/feet)
        
        floor_w_pixels = floor_w*px_per_foot
        floor_h_pixels = floor_h*px_per_foot
        
        xdiff = int((squares - ((floor_w+wall_spaces_ft)/5))//2)
        ydiff = int((squares - ((floor_h+wall_spaces_ft)/5))//2)

        area_sq = int(floor_w/5)*int(floor_h/5)
        percentage_of_canvas = int(100*area_sq/(squares**2))

        masks = []
        if xdiff != 0:
            masks.append({'mask': 'LEFT', 'x':int(xdiff), 'y':squares})
            masks.append({'mask': 'RIGHT', 'x':int(xdiff), 'y':squares})
        if ydiff != 0:
            masks.append({'mask': 'TOP', 'x':int(squares), 'y':int(ydiff)})
            masks.append({'mask': 'BOTTOM', 'x':int(squares), 'y':int(ydiff)})

        areas = 'F and W'
        art_note = ''
        mask_text = '\n'
        art_note_1 = ''
        art_note_2 = '' 
        art_note_3 = ''
        if len(masks) > 0:
            areas = 'F, W, and B'
            art_note = '- ART ILLUMINATIONS (B) must occupy all B characters exactly, with no resizing'
            mask_text = f'''
    STEP 0: Celtic Knotwork Dragon Slab
    The areas marked as B ARE SOLID SLABS OF OBSIDIAN WHOSE UPPER SURFACE (FACING THE CAMERA) CONTAINS {art_theme}
    These should expand to fill the entire B regions, and only B regions,  one on the {masks[0]['mask']} B region, and one on the {masks[1]['mask']} B region
    These are both the same size ({masks[0]['x']}x{masks[0]['y']} units)
    The surfaces are the same height as the tops of the walls in W
    These surfaces are flat, no tilt
    - Top, sides, and edges of these blocks must be fully visible. 
    - Must fill only B region, and fills all of B region
    - THESE ARE IMPORTANT ART ELEMENTS THAT ARE EXTERNAL TO THE ROOM OUTSIDE THE WALLS
    - THEY EXTEND THE ENTIRITY OF THE {masks[0]['mask']} and {masks[1]['mask']} EDGES OF THE MAP, AS SHOWN IN THE ASCII
    - If these seem a little bit large, that is on purpose and the point, just give them more detail.
            '''

            art_note_1 = '[WITH ART BLOCKS]'
            art_note_2 = '\n  • [B] = thick illuminated manuscript stone panels on the {} and on the {}'.format(masks[0]['mask'], {masks[1]['mask']})
            art_note_3 = f'''\n- BOTH ART Blocks must be the same size, {masks[0]['x']}x{masks[0]['y']} units
    - Art Blocks may ONLY appear in B areas, Only at the {masks[0]['mask']} and {masks[1]['mask']} of the image
    - THIS IS NOT A FRAME
    - B AREAS, F AREAS, AND W AREAS MUST BE WHERE THE ASCII MAP INDICATES'''
        room_shape_main = room_shape.split(' ')[0]
        if  room_shape_main == 'Passage':
            room_shape_main = "narrow rectangle"
        elif room_shape_main.lower() == 'rectangle' and max([floor_w, floor_h])/min([floor_w, floor_h]) >= 2:
             room_shape_main = "narrow rectangle"
        size_exp = ''
        if max([floor_w, floor_h])/min([floor_w, floor_h]) >= 3:
            size_exp = size_exp + f'''This room is intentionally extremely narrow.  Please Keep the ratio {floor_ratio}\n'''

        #Floor coordinates
        diffx = floor_width/2
        diffy = floor_height/2

        fx1 = int(squares/2) - diffx
        fx2 = int(squares/2) + diffx
        fy1 = int(squares/2) - diffy
        fy2 = int(squares/2) + diffy

        #WALL coordinates
        ndiffx = (floor_width + int(wall_spaces_ft/5))/2
        ndiffy = (floor_height + int(wall_spaces_ft/5))/2
        wx1 = int(squares/2) - ndiffx
        wx2 = int(squares/2) + ndiffx
        wy1 = int(squares/2) - ndiffy
        wy2 = int(squares/2) + ndiffy

        layout_lst = [] 
        for r in range(int(squares)):
            row = ''
            for c in range(int(squares)):
                if c >= fx1 and c< fx2 and r >= fy1 and r < fy2:
                    row = row + '[F]'
                elif c >= wx1 and c< wx2 and r >= wy1 and r < wy2:
                    row = row + '[W]'
                else:
                    row = row + '[B]'
            layout_lst.append(row)
        layout = '\n'.join(layout_lst)
        
        prompt = f'''***REALISTIC TOP-DOWN ORTHOGRAPHIC BATTLEMAP WITH VISUAL WALLS - {room_shape_main.upper()} {room_theme.upper()} {art_note_1.upper()}***

    CANVAS & MASKING
    - Canvas size: {int(squares)}×{int(squares)} units
    - This is the exact ASCII canvas layout (non-negotiable blueprint - Final Image Must Match):
    {layout}


    BOUNDARY COLLISION — NON-NEGOTIABLE
    - Treat each ASCII region as a PHYSICAL OBJECT with hard edges:
      • [F] = a flat stone floor slab inset into the center
      • [W] = a vertical 3D wall ring rising from its own footprint {art_note_2}
    - Every boundary between {areas} is a HARD PHYSICAL EDGE.
    - The AI must treat the ASCII blueprint as the literal final composition.
    - The final image must match the ASCII canvas aspect ratio exactly ({int(squares)}×{int(squares)}).
    - Do NOT zoom, crop, reframe, center, scale, or expand the scene.
    - The camera is locked directly above the canvas in strict orthographic view.
    - The camera cannot automatically "square", "fill space", or "expand" an area.
    - No artistic reinterpretation of framing is allowed.

    {areas.upper()} GEOMETRY LOCK
    - The bounding boxes of {areas} regions are physically fixed.
    - Their proportions and locations cannot be changed, expanded, centered, or stretched.
    - Each {areas} = exactly 1×1 unit
    - {areas} are mutually exclusive
    - Do NOT scale, stretch, move, rotate, or distort any element
    - Floor (F) must occupy all F characters exactly
    - Walls (W) must occupy all W characters exactly {art_note}
    - Doors are along F adjacent to W, with their bottoms touching the W/F Border
    - Do NOT reframe, reposition, zoom, crop, recompose, or reinterpret the spatial layout.
    - Render the scene locked to the ASCII grid exactly as written.
    {mask_text}

    STEP 1: FLOOR ("F" - PRIMARY, FIXED GEOMETRY — NON-NEGOTIABLE)
    - Strict top-down orthographic view, no tilt
    - Floor shape: {room_shape_main}
    - Floor dimensions: {floor_width}×{floor_height} grid units ({floor_ratio} ratio)
    - Floor must render at exact {floor_ratio} aspect ratio, no rotation, stretching, resizing, cropping, or movement allowed
    - Floor material: {floor_material}

    BATTLEMAP FLOOR GRID:
    - Override all natural stone patterns.
    - Each grid tile is EXACTLY 1×1 unit with sharp straight seams.
    - Grid dimensions: {floor_width} columns × {floor_height} rows ({floor_ratio} ratio)
    - The grid lines MUST be visible as thin seams between every F cell.
    - Absolutely no variation in tile size or shape.
    - Treat the grid as a PHYSICAL arrangement of square tiles, not drawn lines.

    STEP 2: WALLS ("W" - ADDED AFTER FLOOR — MAY NOT CHANGE FLOOR SIZE) -> Do After Floor Drawn
    - Wall material: {wall_material}
    - All inward-facing wall surfaces must be fully visible, including the SOUTH wall
    - EVRY WALL MUST HAVE A VISIBLE INWARD FACE
    - Classic JRPG / dungeon-crawler style: vertical edges with slight inward lean
    - Maximum lean: 5–10° inward only.
    - no rotation, stretching, resizing, cropping, or movement allowed of walls

    STEP 3: DOOR ORIENTATION & PLACEMENT (UNAMBIGUOUS) -> Place on Walls once walls are done
    - Each door is a rectangle along the wall, projecting inward from floor edge
    - Doors must be perpendicular to F, flush with floor, no rotation or gap
    - Doors are {int(200/max([floor_w, floor_h]))}% the height of the wall
    - THERE ARE exactly {len(doors)} DOORS:
    {doors_text}

    STEP 4: CONTENTS & ATMOSPHERE [Visual Only & realistic, inside F or W] -> Do not block doors
    ROOM PURPOSE: {room_theme}
    {contents_text}
    - All items remain strictly top-down unless on walls (rendered in W space)
    - Each Space represents 5ft, make sure items are realistic given that scale

    CRITICAL NON-NEGOTIABLES
    - F must be orthographic top-down, exact grid, no tilt, and {floor_ratio}{art_note_3}
    - Grid must be {floor_width} columns × {floor_height} rows, each tile EXACTLY 1×1 unit with sharp straight seams.
    - ALL AND ONLY {len(doors)} MUST BE DRAWN ON W SPACES BOTTOMS ON F SPACES
    - ONLY THE ROOM SPECIFIED IS TO BE DRAWN -> NO OTHER GEOGRAPHY
    - DO NOT RESHAPE {areas} FOR ANY REASON
    - ALL 4 INNER WALLS MUST BE VISIBLE WITH 5% INWARD TILT, INCLUDING SOUTH


    ***Use Realistic Colors and Textures***
        '''
        if debug:
            print(prompt)
            return prompt

        return prompt

    def render_image(self, room_id, file_name, query, model="openai/gpt-5-image-mini"):
        # ------------------
        # CONFIG
        # ------------------
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
           "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": query
                }
            ],
            "modalities": ["image", "text"]
        }
        
        # ------------------
        # REQUEST
        # ------------------
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        try:
            self.rooms[room_id]['image result'] = result
        except:
            print('not a room')
        
        # ------------------
        # HANDLE RESPONSE
        # ------------------
        if "choices" not in result or not result["choices"]:
            print("No response choices returned.")
            print(result)

        message = result["choices"][0].get("message", {})
     
        if "images" not in message or not message["images"]:
            print("No images returned.")
            print(message)
        
        # Extract first image
        img_data_url = message["images"][0]["image_url"]["url"]
        
        # A data URL looks like: data:image/png;base64,AAAA...
        if "," not in img_data_url:
            raise ValueError("Invalid image data URL format.")
        
        base64_data = img_data_url.split(",")[1]  # strip the prefix
        
        # ------------------
        # SAVE IMAGE
        # ------------------
        
        output_path = self.file_path(file_name)

     
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(base64_data))
                
    
       
    ## MATH & WORKERS       
    def shift_from_wall(self, pos, facing, wall):
        '''
        pos: (ew, ns, ud)
        facing: 'n', 's', 'e', 'w'
        wall: one of
            'Wall opposite entrance',
            'Same wall as entrance',
            'Wall left of entrance',
            'Wall right of entrance'
        '''
    
        # Movement vectors in (east-west, north-south)
        vectors = {
            'n': (0, 1),
            's': (0, -1),
            'e': (1, 0),
            'w': (-1, 0)
        }
    
        # Map walls to relative movement directions
        relative = {
            'Same wall as entrance': 'back',
            'Wall opposite entrance': 'forward',
            'Wall left of entrance': 'left',
            'Wall right of entrance': 'right'
        }
    
        # Facing → relative direction → absolute axis movement
        facing_map = {
            'n': {'forward': 'n', 'back': 's', 'left': 'w', 'right': 'e'},
            's': {'forward': 's', 'back': 'n', 'left': 'e', 'right': 'w'},
            'e': {'forward': 'e', 'back': 'w', 'left': 'n', 'right': 's'},
            'w': {'forward': 'w', 'back': 'e', 'left': 's', 'right': 'n'}
        }
    
        # Determine absolute direction to move
        rel_dir = relative[wall]
        abs_dir = facing_map[facing][rel_dir]
    
        dx, dy = vectors[abs_dir]
        ew, ns, ud = pos
        return (ew + dx, ns + dy, ud), abs_dir
    
    def get_image_ratio(self, dimensions):
        '''
        '''
        nd = min(dimensions)
        xd = max(dimensions)
        my_mod = 1
        denom = nd+1
        while my_mod != 0:
            denom = denom-1
            my_mod = max(nd%denom, xd%denom)
        return('{}:{}'.format(int(dimensions[0]/denom), int(dimensions[1]/denom)))
    
    ### Initialization
    def new_door(self, door_location, exit=False, passage = False, location = None):
        '''
        Creates a door, assuming the destination doesn't already exist (would already have a door there if it did)
        '''
        if location == None:
            location = self.Current_Location
        
        # determine
        tup, wall = self.shift_from_wall(location, self.Current_Orientation, door_location)
        coord = str(tuple(sorted([location, tup])))

        # make sure door doesn't already exist and location isn't already spoken for
        if str(tup[0]) not in self.locations.keys() and coord not in self.doors.keys():
            self.doors[coord] = {}
            self.doors[coord]['exit'] = exit
            if passage == True:
                width = sorted((self.roll(self.AppendixA['Passage Width']), self.roll(self.AppendixA['Passage Width'])))[0]
                self.doors[coord]['door type'] = ' {} passage leading 10ft. into darkness'.format(width)
            else:
                self.doors[coord]['door type'] = self.roll(self.AppendixA['Door Type'])
            
    def new_room(self, room='Chamber', start=False):
        '''
        Makes doors, rolls for room, finds exits, etc.
        '''
        # Determine room_id and whether this is the start room
        try:
            room_id = max(self.rooms.keys()) + 1
        except ValueError:
            room_id = 0
            self.Current_Location = (0,0,0)
            start = True
        
        # --- ROOM GENERATION LOOP -----------------------------
        current_level = self.Current_Location[2]
        purpose_key = self.levels.loc[self.levels['level'] == current_level, 'purpose'].values[0]
        while True: 
            if start:
                room_desc = self.roll(self.AppendixA['Starting Area'])
                self.Current_Orientation = input('What Direction is the Entrance?')[:1].lower()
                room_purpose = 'Main entrance to the dungeon'
            
                #entrance door...
                self.new_door('Same wall as entrance', exit=True, passage = False)
                self.locations[str(self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Same wall as entrance')[0])] = -1
                
            else:
                room_desc = self.roll(self.AppendixA[room])
                while room_desc == 'Chamber (roll on the Chamber table)':
                    room = 'Chamber'
                    room_desc = self.roll(self.AppendixA[room])
                room_purpose = self.roll(self.AppendixA['Purpose'][purpose_key])

            # --- DIMENSIONS -----------------------------------
            print(room_desc)
            if room_desc.lower().find('circle') > -1:
                size = room_desc.split(' ft')[0][-2:]
                dimensions = [int(size), int(size)]
            elif room_desc.lower().find('passage') > -1 or room=='Passage':
                a = self.roll(self.AppendixA['Passage Width'])
                width = int(a[:2])
                if width > 10:
                    dimensions = [width, 80]
                else:
                    dimensions = [width, 40]
                    room_purpose = 'Hallway'
                room_desc = 'Passage ' + a + ' wide and {} ft long '.format(dimensions[1])
            else:
                segment = room_desc[room_desc.find('×') - 3 : room_desc.find('×') + 4]
                dimensions = [int(a) for a in segment.split(' × ')]



            # --- CHECK FIT -------------------------------------
            locations = []
            locations.append(self.Current_Location)
            fits = True

            def is_blocked(loc):
                return str(loc) in self.locations

            width, height = map(int, dimensions)

            # Check vertical extension
            if height > 40:
                loc = self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Wall opposite entrance')[0]
                if is_blocked(loc):
                    fits = False
                else:
                    locations.append(loc)

            # Check horizontal extension
            if width > 40:
                loc_right = self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Wall right of entrance')[0]
                loc_left  = self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Wall left of entrance')[0]

                # pick whichever side is free
                loc = None
                if not is_blocked(loc_right):
                    loc = loc_right
                elif not is_blocked(loc_left):
                    loc = loc_left
                else:
                    fits = False

                if loc:
                    locations.append(loc)

                    # if also tall, check far corner
                    if height > 40:
                        last = self.shift_from_wall(loc, self.Current_Orientation, 'Wall opposite entrance')[0]
                        if is_blocked(last):
                            fits = False
                        else:
                            locations.append(last)

            if fits:
                break

        # --- MARK LOCATIONS WITH ROOM ID ----------------------
        for loc in locations:
            self.locations[str(loc)] = room_id

        # --- EXIT / DOOR GENERATION ---------------------------
        if len(locations) > 1:
            exit_key = '2'
        else:
            exit_key = '1'
        
        exits = int(self.roll(self.AppendixA[f'Chamber_Exits_{exit_key}']))
        if start and exits < 4:
            exits = 4

        # Collect existing doors touching any room tile
        def collect_doors():
            found = []
            for loc in locations:
                for key in self.doors:
                    if str(loc) in key:
                        found.append(key)
            return found

        doors = collect_doors()

        # Create new doors until we have enough
        location = self.Current_Location
        while len(doors) < exits:
            door_loc = self.roll(self.AppendixA['Exit Location'])
            
            tup, wall = self.shift_from_wall(location, self.Current_Orientation, door_loc)

            if tup in locations:
                location = tup

            self.new_door(door_loc, exit=False, passage=False, location=location)
            doors = collect_doors()
            
            
        # dimensions are give width-length from observer...need ew by ns
        if self.Current_Orientation in ['e','w']:
            
            dimensions.reverse()
       
        self.make_room(room_desc, room_purpose, locations, room_id, dimensions)

    def make_room(self, room, room_purpose, locations, room_id, dimensions):
        self.rooms[room_id] = {}
        self.rooms[room_id]['locations'] = locations
        self.rooms[room_id]['shape'] = room
        self.rooms[room_id]['purpose'] = room_purpose
        
        doors = []
        door_location = {'(0, -1, 0)' : 'south',
                 '(0, 1, 0)' : 'north',
                 '(1, 0, 0)' : 'east',
                 '(-1, 0, 0)' : 'west'}
        locations.sort()

        units = [1,1]
        for loc in locations:
            placefinder = [loc[i] - locations[0][i] for i in range(3)]
            units = [units[i] + placefinder[i] for i in range(2)]
        divs = [dimensions[i]/units[i] for i in range(2)]
        for loc in locations:
            for key in self.doors.keys():
                if key.find(str(loc)) > -1:
                    door = {}
                    door['type'] = self.doors[key]['door type']
                    dif = key.replace(str(loc),'').replace(', (','').replace('), ','').replace(')','').replace('(','')
                    dif = tuple([int(a) - int(loc[i]) for i, a in enumerate(dif.split(','))])
                    placefinder = [loc[i] - locations[0][i] for i in range(3)]
                    if door['type'].lower().find('secret') == -1:
                        door['wall'] = door_location[str(dif)]
                        if door['type'].lower().find('p') > -1:
                            door['width_ft'] = 8
                        else:
                            door['width_ft'] = 4
                        #door location along wall -> door['placement'] = (numerator along wall, denominator along wall)
                        if door['wall'] == 'north' or door['wall'] == 'south':  # x is relevant
                           door['placement'] = (int(placefinder[0]*divs[0] + divs[0]/2),dimensions[0])
                        elif door['wall'] == 'east' or door['wall'] == 'west':
                            door['placement'] = (int(placefinder[1]*divs[1] + divs[1]/2),dimensions[1])
                        doors.append(door)
        walls = self.levels[self.levels['level'] == self.Current_Location[2]]['walls'].values[0]
        floors = self.levels[self.levels['level'] == self.Current_Location[2]]['floors'].values[0]
        ceilings = self.levels[self.levels['level'] == self.Current_Location[2]]['ceilings'].values[0]
        
        # check contents...
        contents = []
        for key in self.AppendixA['Dungeon Dressings'].keys():
            if key != 'General Furnishings and Appointments' and key != 'Specific':
                for i in range(len(locations)+random.randint(1,3)):
                    thing =  self.roll(self.AppendixA['Dungeon Dressings'][key])
                contents.append(key + ': ' + thing)
            elif key == 'Specific' and room != 'Passage':
                things = []
                for kkey in self.AppendixA['Dungeon Dressings']['Specific'].keys():
                    for word in kkey.split(' '):
                        if room_purpose.find(word.lower()) > -1:
                            for i in range(len(locations)+random.randint(1,3)):
                                things.append(self.roll(self.AppendixA['Dungeon Dressings']['Specific'][kkey]))
                contents.append('Specific Furnishings:' + ', '.join(things))
            else:
                things = []
                for loc in locations:
                    things.append(self.roll(self.AppendixA['Dungeon Dressings'][key]))
                self.rooms[room_id][key] = things
                contents.append(key + ': ' + ', '.join(things))
        Current_State = self.roll(self.AppendixA['Current_Chamber_State'])
        if Current_State.find('Converted')>-1 and room !='Passage':
            Current_State = 'now used as/has furniture for {}'.format(self.roll(self.AppendixA['Purpose']['General Dungeon Chambers']))
            contents.append('Additional Themed Furniture and Room State: {}'.format(Current_State))

        # calculate the dimensions for gpt5-image-mini
        scale = 14 #14 pixels = 1 ft.
        x = (dimensions[0]+10)*scale
        y = (dimensions[1]+10)*scale
        canvas_w = 1024
        canvas_h = 1024
        while x > 1024 or y > 1024:
            scale = scale -1
            x = (dimensions[0]+10)*scale
            y = (dimensions[1]+10)*scale

        # generate the prompt

        image_prompt = self.build_battlemap_prompt(canvas_w = canvas_w
                                           , canvas_h = canvas_h
                                           , floor_w = dimensions[0] # in ft
                                           , floor_h = dimensions[1] # in ft
                                           , grid_px = scale*5
                                           , room_shape = room
                                           , room_theme = room_purpose
                                           , floor_material = floors
                                           , wall_material = walls
                                           , doors = doors
                                           , contents = contents
                                           , debug = False)
                                           
                                           

        print(image_prompt)
        retry = True
        fails = 1
        file_name = self.file_path('{} room {}.png'.format(self.filename, room_id))
        # try my old version first...
        prompt = image_prompt
        model = "openai/gpt-5-image-mini"
        while retry:
            self.render_image(room_id, file_name, prompt, model=model)
        
            # Load the image
            img = mpimg.imread(file_name)  # Replace "your_image.png" with your image file path

            # Display the image
            plt.imshow(img)
            plt.axis('off')
            plt.show()
            good = input('Does this look like {} {}?'.format(room, room_purpose))
            if good.lower()[0] == 'y':
                retry = False
                folder = self.file_path('success').replace("\\\\", "\\")
                try:
                    shutil.move(file_name, folder)
                except:
                    os.system('del {}/{}'.format(folder, file_name))
                    shutil.move(file_name, folder)
                self.rooms[room_id]['image'] = self.file_path('success/{} room {}.png'.format(self.filename, room_id))
                img = mpimg.imread(self.file_path('success/{} room {}.png'.format(self.filename, room_id)))  # Replace "your_image.png" with your image file path
                print('Showing Again')
                # Display the image
                plt.imshow(img)
                plt.axis('off')
                plt.show()
            else:
                print('trying again...')
                move_file = True
                while move_file:
                    try:
                        folder = self.file_path('fail').replace("\\\\", "\\")
                        new_filename = file_name.replace('.png','fail{}.png'.format(fails))
                        fails +=1
                        os.rename(file_name, new_filename)
                        shutil.move(new_filename, folder)
                        move_file = False
                    except:
                        print('trying again... {}'.format(fails))
                        move_file = False

    def new_stairs(self, destination, door_id):
        '''
        '''
        stairdct = {'up one level': 1
                   , 'down one level': -1
                   , 'down two levels': -2
                   , 'down three levels': -3
                   , 'up two levels': 2
                   , 'dead end': 9001}
        possible = False
        tries = 0
        while not possible and tries < 10:
            result = self.roll(self.AppendixA['Stairs'])
            #directions
            directions = []
            destinations_new = []
            [directions.append(stairdct[key]) for key in stairdct.keys() if result.lower().find(key) > -1]
            tries += 1
            #check if the level exists...
            fits = 0
            for dr in directions:
                tt = (0,0,dr)
                temp = tuple([int(a) + tt[i] for i, a in enumerate(destination.split(','))])
                if self.levels[self.levels['level'] == self.Current_Location[2]+dr].shape[0] > 0 and str(temp) not in self.locations.keys():
                    destinations_new.append(temp)
                    possible = True
        self.doors[door_id]['Stairs'] = destinations_new
        if possible == True:
            # we have stairs

           
            # block all locations that can't be used...
            dest = str(tuple([int(a) for a in destination.split(',')]))
            self.locations[dest] = {}
            self.locations[dest]['Stairs'] = destinations_new

            for nd in destinations_new:
                # add doors from destinations_new to origin on same floor
                ndoor = ', '.join([a if a.find(')') == -1 else a.replace(a.split(')')[0],str(nd[2])) for a in door_id.split(',')])
                self.doors[ndoor] = self.doors[door_id]
            if len(destinations_new) > 1:
                choice = ' '
                while choice.lower()[0] not in ['u', 'd']:
                    choice = input('Up or down?')
                if choice == 'u':
                    ndestination = destinations_new[1]
                else:
                    ndestination = destinations_new[0]
            else:
                self.doors[door_id]['Stairs'] = True
                ndestination = destinations_new[0]
            self.Current_Location = ndestination
            
            if result.lower().find('passage') > -1:
                self.new_room(room='Passage')
            else:
                self.new_room(room='Chamber')
        else:  #just make a room...
            self.Current_Location = destination
            # self.new_room(room=result)
        return tries    
        
    def get_orientation(self, door_key, destination):
        destination = str(destination)
        origin = door_key.replace(destination,'').replace(', )','').replace('(, ','').replace('(','').replace(')','').replace(' ','').split(',')
        destination = destination.replace('(','').replace(')','').replace(' ','').split(',')
        print(origin, destination)
        orient_dct = {'(0, -1, 0)' : 's',
                      '(0, 1, 0)' : 'n',
                      '(1, 0, 0)' : 'e',
                      '(-1, 0, 0)' : 'w'}
        return orient_dct[str(tuple([int(d)-int(origin[i]) for i, d in enumerate(destination)]))]

     
    ### Movement
    def open_door(self, door_key):
        '''
        They try to open a door
        '''
        #detemrine destination
        destination = door_key
        locations = self.rooms[self.locations[str(self.Current_Location)]]['locations']
        for loc in locations:
            destination = destination.replace(str(loc),'')
        destination = destination.replace('((','(').replace('))',')').replace(', )','').replace('(, ','')
        destination = tuple([int(a) for a in destination.replace('(','').replace(')','').split(', ')])
        # orientation
        self.Current_Orientation = self.get_orientation(door_key, destination)
        # what's beyound the door?
        result = self.roll(self.AppendixA['Beyond Door'])
        print(result)
        result = result.split(' ')[0]

        if result == 'False':
            self.locations[destination] = -2
            print('ADD TRAP HERE')
        elif result == 'Stairs':
            print('ADD STAIRS HERE')
        else:
            self.Current_Location = destination
            self.new_room(room=result)
            
 """   
    
    
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

def random_color():
    return '#' + ''.join([random.choice('0123456789') for i in range(6)])

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
 
def get_figsize_from_wallborders(wallborders, dpi=100, pixels_per_unit=80, padding_units=1):
    """
    Calculate matplotlib figsize from wallborders coordinates.
    
    Args:
        wallborders:     List of line segments defining the outer walls
        dpi:             DPI for the figure
        pixels_per_unit: How many pixels per grid unit
        padding_units:   Extra units of black border around the room (the "mask" area)
    
    Returns:
        figsize: (width, height) in inches for plt.figure()
        xlim:    (xmin, xmax) for plt.xlim()
        ylim:    (ymin, ymax) for plt.ylim()
    """
    # Flatten all points from all segments
    all_points = [pt for segment in wallborders for pt in segment]
    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]

    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    # Add padding for the black border around the room
    xmin -= padding_units
    xmax += padding_units
    ymin -= padding_units
    ymax += padding_units

    x_units = xmax - xmin
    y_units = ymax - ymin

    width_px  = x_units * pixels_per_unit
    height_px = y_units * pixels_per_unit

    figsize = (width_px / dpi, height_px / dpi)

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

##############
# Core classes
##############
class Position():
    '''
    position is a tuple, (x, y)
    '''
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x = x
        self.y = y

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
    __slots__ = ('position', 'direction', 'internal', 'can_has_door', 'used', 'door')

    def __init__(self, position, direction):
        self.position = position
        self.direction = direction
        self.internal = False
        self.can_has_door = False
        self.used = False
        self.door = None

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
    __slots__ = ('position','borders')
   
    def __init__(self, position):
        self.position = position

        self.borders = {DIRECTION.RIGHT: Border(position, DIRECTION.RIGHT),
                        DIRECTION.LEFT: Border(position, DIRECTION.LEFT),
                        DIRECTION.UP: Border(position, DIRECTION.UP),
                        DIRECTION.DOWN: Border(position, DIRECTION.DOWN)}
    
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
    __slots__ = ('room_id', 'blocks','color', 'doors', 'is_exit', 'purpose', 'state', 'contents', 'parent', 'monster', 'treasure', 'furnishings', 'traps', 'hazards', 'hallway', 'stairs', 'description')

    def __init__(self, parent, position=Position(0,0), hallway=False, stairs=None, is_exit=False):      
        self.blocks = [Block(position)]
        self.color = random_color()
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
        max_x_num, max_y_num, min_x_num, min_y_num = 0, 0, 0, 0
        min_distance_to_center = 90001
        
        for border in borders:
            x, y = border.position.point()
            if x < min_x:
                min_x = x
                min_x_num = 0
            elif x > max_x:
                max_x = x
                max_x_num = 0
            if y < min_y:
                min_y = y
                min_y_num = 0
            elif y > max_y:
                max_y = y
                max_y_num = 0
                
            if x == max_x:
                max_x_num += 1
            elif x == min_x:
                min_x_num += 1
            if y == max_y:
                max_y_num += 1
            elif y == min_y:
                min_y_num += 1
            distance_to_center = get_distance((0,0), (x,y))
            if distance_to_center < min_distance_to_center:
                min_distance_to_center = distance_to_center
                 
        mid_x = int((max_x + min_x)/2)
        mid_y = int((max_y + min_y)/2)
        check_xy = max(min_x_num, max_x_num, min_y_num, min_x_num) + 1
        
        # add extreme borders to list for more liklyhood of choice
        temp = [border for border in self.borders() if not border.internal]
        if t_pass:
            temp = []
            
        for border in borders:
            x, y = border.position.point()

            if x == max_x:
                [temp.append(border) for _ in range(check_xy-max_x_num)]
                if t_pass:
                    [temp.append(border) for _ in range(check_xy)]
            elif x == min_x:
                [temp.append(border) for _ in range(check_xy-min_x_num)]
                if t_pass:
                    [temp.append(border) for _ in range(check_xy)]
            
            if y == max_y:
                [temp.append(border) for _ in range(check_xy-max_y_num)]
                # t-passage ends should have it...
                if t_pass:
                    [temp.append(border) for _ in range(check_xy)]
            elif y == min_y:
                [temp.append(border) for _ in range(check_xy-min_y_num)]
                if t_pass:
                    [temp.append(border) for _ in range(check_xy)]
            
            if not t_pass: # middle sections
                if x >= mid_x-1 and x <= mid_x + 1 and y <= max_y-1 and y >= min_y+1:
                    [temp.append(border) for _ in range(int(check_xy))]
                if y >= mid_y - 1 and y >= mid_y+1 and x <= max_x-1 and x >= min_x+1:
                    [temp.append(border) for _ in range(int(check_xy))]

            # lets try to make sure the dungeon centers...   
            if get_distance((0,0), (x,y)) >= min_distance_to_center+1 and not t_pass:
                [temp.append(border) for _ in range(int(check_xy))]


        neighbors = set()
        directions = set()
        attempts = 0

        while len(self.doors) < number and attempts <= len(borders):
            border = random.sample(borders, 1)[0]
            check_position = border.position
            check_direction = border.direction
            okay = True
            
            if check_position in neighbors:  #borders an existing door
                okay = False
            elif len(list(directions)) < 4 and check_direction in directions and not t_pass:  #same wall...
                okay = False
            if okay == True:
                neighbors.add(check_position)
                border.can_has_door = True
                door = Door(parent=self)
                door.borders.append(border)
                door.rooms.append(self)
                border.door = door
                self.doors.append(door)
                neighbors.update(border.position.area())
                directions.add(check_direction)
                if trapped == True:
                    door.trapped = True
            attempts += 1
                      
    def make_circle(self, diameter):
        '''
        Starts a circle from the firs position...
        '''
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
        '''
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
  
    def clear_room(self, clear_all = True):
        
        self.contents = 'Empty room'
        self.monster = ''
        self.traps = ''
        self.hazards = ''
        self.treasure = ''
        if clear_all:
            self.furnishings = []
        
    def stock_room(self, hallway=False):
        '''
        '''
        # Purpose, it's that little flame...
        if self.hallway:
            self.purpose = 'Hallway'
        elif self.stairs != None:
            self.purpose = 'Stairs'
        elif self.is_exit == True:
            self.purpose = 'Exit (not a real room)'
            self.color = '#000000'
        else:
            try:
                self.purpose = self.parent.parent.roll_table(self.parent.parent.AppendixA['Purpose'][self.parent.info['purpose']])
            except KeyError:
                self.purpose = self.parent.parent.roll_table(self.parent.parent.AppendixA['Purpose']['General Dungeon Chambers'])
        self.state = self.parent.parent.roll_table(self.parent.parent.AppendixA['Current_Chamber_State'])

        if self.hallway == True or self.stairs != None or self.is_exit == True:
            self.contents = 'Empty room'
        else:
            self.contents =  self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Chamber Contents'])
        
            if 'Monster' in self.contents:
                mon_type = self.contents.split(')')[0]+')'
                monlist = self.parent.info[mon_type].split(', ')
                self.monster = random.sample(monlist,1)[0]
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
                CR = 3+2*abs(int((self.parent.info['level'])))
                if 'incidental' in self.contents:
                    hoard = False
                else:
                    hoard = True
                self.treasure = self.parent.parent.get_treasure(CR, hoard)
        
        
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
    __slots__ = ('parent', 'borders', 'door_type', 'rooms', 'trapped', 'trap')
    
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
        if self.trapped == True:
            self.traps = 'Trap({}):{} [Trigger: Opening the door]'.format(self.parent.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Damage Severity'])
                                                         , self.parent.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Effects']))
    
class Corridor():
    __slots__ = ('start_border', 'stop_border', 'path')

    def __init__(self, start_border, stop_border, path):
        self.start_border = start_border
        self.stop_border = stop_border
        self.path = path

    def geometry_segments(self):
        points = [self.start_border.connection_point()]

        points.extend(position.move(0.5, 0.5).point() for position in self.path)

        points.append(self.stop_border.connection_point())

        return points

class Dungeon():
    __slots__ = ('rooms','corridors','level', 'info', 'parent')

    def __init__(self, info=None, parent=None):
        self.rooms = []
        self.corridors = []
        self.info = info
        self.parent = parent
        self.level = self.info['level']

    def create_room(self, blocks, doors, trap=False, is_exit=False):
        room = Room(self, is_exit=is_exit)

        for i in range(blocks):
            room.expand()

        room.place_doors(doors, trap)

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
        
        for room in self.rooms:
            for door_border in room.door_borders():
                plt.plot(*zip(*door_border.geometry_borders()), color='b', linewidth=6, alpha=0.75)
            

        for corridor in self.corridors:
            plt.plot(*zip(*corridor.geometry_segments()), color='#000000', linewidth=1, alpha=1)

        plt.savefig(self.parent.file_path("Maps/{} level {}.png".format(self.parent.filename, self.info['level'])), dpi=300, bbox_inches='tight')
        if show == True:
            plt.show()
        
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
        for border in door.borders:
            border.used = False
            border.can_has_door = False
            border.door = None
        for room in door.rooms:
            try:
                room.doors.pop(room.doors.index(door))
            except:
                print("door wasn't in room?")
        del door
    
    def connect_free_doors(self, max_distance):
        free_doors = self.get_free_doors()
        connections = []

        for dungeon_door in free_doors:

            for other_door in free_doors:

                if other_door is dungeon_door:
                    continue

                # --- Doors must face each other ---
                if dungeon_door.borders[0].mirror().direction != other_door.borders[0].direction:
                    continue

                room_a = dungeon_door.rooms[0]
                room_b = other_door.rooms[0]

                if room_a is room_b:
                    continue

                # -------------------------------------------------
                # Candidate borders on each room (external only)
                # -------------------------------------------------

                dborders = [
                    b for b in room_a.borders()
                    if not b.internal
                    and b.direction == dungeon_door.borders[0].direction
                ]

                oborders = [
                    b for b in room_b.borders()
                    if not b.internal
                    and b.direction == other_door.borders[0].direction
                ]

                if not dborders or not oborders:
                    continue

                # -------------------------------------------------
                # Find closest border pair
                # -------------------------------------------------

                candidates = []

                for db in dborders:
                    for ob in oborders:
                        dist = get_distance(
                            db.position.point(),
                            ob.position.point()
                        )
                        candidates.append((dist, db, ob))

                dist, db, ob = min(candidates, key=lambda x: x[0])

                if dist >= max_distance:
                    continue

                # -------------------------------------------------
                # Pathfinding validation
                # -------------------------------------------------

                try:
                    filled = room_a.block_positions() | room_b.block_positions()

                    path_length, path = find_path(
                        ob.mirror().position,
                        db.mirror().position,
                        filled_cells=filled,
                        max_path_length=max_distance
                    )
                except Exception:
                    path_length = None

                if path_length is None or path_length >= max_distance:
                    continue

                # =================================================
                # ✅ VALID CONNECTION — MOVE SINGLE DOOR OBJECT
                # =================================================

                # ---- Clear OLD borders (door currently occupies them) ----
                for border in dungeon_door.borders:
                    border.used = False
                    border.can_has_door = False
                    border.door = None

                for border in other_door.borders:
                    border.used = False
                    border.can_has_door = False
                    border.door = None

                # ---- Remove other_door from its room ----
                if other_door in room_b.doors:
                    room_b.doors.remove(other_door)

                # -------------------------------------------------
                # Assign NEW borders to dungeon_door
                # -------------------------------------------------

                dungeon_door.borders = [db, ob]

                db.used = ob.used = True
                db.can_has_door = ob.can_has_door = True
                db.door = ob.door = dungeon_door

                # ---- Update room connections ----
                if room_b not in dungeon_door.rooms:
                    dungeon_door.rooms.append(room_b)

                if dungeon_door not in room_b.doors:
                    room_b.doors.append(dungeon_door)

                # -------------------------------------------------
                # Create corridor
                # -------------------------------------------------

                new_corridor = Corridor(db, ob, path)
                self.corridors.append(new_corridor)

                connections.append((room_a, room_b, dungeon_door))

        return connections
               
    def add_area(self):
        '''
        Rolls on some tables from the DMG
        '''
        stairs = False
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
                if d20 <= 2:
                    # Passage extending 10 ft., then T intersection extending 10 ft. to the right and left
                    new_room = self.create_tpassage(3)
                elif d20 > 2 and d20 <= 8:
                    # Passage 20 ft. straight ahead
                    new_room = self.create_rectangle_room(10*random.randint(2,10),10,random.randint(3,4))
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
                if nd20 <= 12 or nd20 == 16 or nd20 == 18:
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
The floor is ONLY for the area defined by the floor mask in mask.png. Do NOT extend floor textures onto the white wall trapezoids. MASK IS A HARD CLIPPING PATH. The black pixels in MASK.png are a physical void.
2. STAIR HEIGHT VS WALLS
The stairs are physical stone blocks that are attached to the vertical walls. The walls represented by white trapezoids must look like 90-degree upright surfaces rather than flat floor. 
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
- Black lines in mask.png mark hard barriers between textures, the square is the landing, the trapezoid the door, the X the edges of the walls, the circle the pillar.

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
            self.connect_free_doors(max_distance=3)
            
            