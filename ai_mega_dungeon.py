import os
import json
import shutil
import pickle
import base64
import openai
import requests
import pandas as pd
import random as rand
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import enum
import heapq
import random
import collections




class AIMegaDungeon:
    _slots_ = ('levels', 'level_info')
    
    def __init__(self, filename=None, levelfile='levels.csv', keys='|'):
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
        new = 0
        if filename != None: #load the old file
            new = self.load(filename)
            self.filename = filename        
            self.levelsdf = pd.read_csv(self.file_path(levels), sep='\t')
            new = 1
        if new == 0: # need a new instance
            self.filename = 'test' # input('Name this dungeon:')
            self.levelsdf = pd.read_csv(self.file_path(levelfile), sep='\t')
            
            
            
            with open(self.file_path('AppendixA.pickle'), 'rb') as file:   
                self.AppendixA = pickle.load(file)
            print('Dungeon {} Created'.format(filename))
            
        self.char_level_ave = 1

 
    ## ADMIN FUNCTIONS
    def file_path(self, filename):
        return os.path.join(self.current_dir, '{}'.format(filename))
        
    def roll_table(self, df):
        droll = rand.randint(1,max(df['Roll']))
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
        
        
    
    """
    def load(self, filename=None):
            try:
                with open(filename+'.aad', 'rb') as file:    
                    dct = pickle.load(file)
            except:
                return 0
            self.map = dct['map'] 
            self.rooms = dct['rooms']
            self.doors = dct['doors'] 
            self.levels = dct['levels'] 
            self.locations = dct['locations']
            self.Current_Orientation, self.Current_Room, self.Current_Location = dct['vars']
            print('{} Loaded Successfully')
            return 1
           
    def save(self, filename='QuickSave'):
        dct = {}
        dct['map'] = self.map
        dct['rooms'] = self.rooms
        dct['doors'] = self.doors
        dct['levels'] = self.levels
        dct['vars'] = (self.Current_Orientation, self.Current_Room, self.Current_Location)
        sct['locations'] = self.locations
        with open(filename+'.aad', 'wb') as file:
            pickle.dump(dct, file)  
        
    def roll(self, df):
        droll = rand.randint(1,max(df['Roll']))
        return df[df['Roll']==droll]['Result'].values[0]
        
    ### AI CALLS     
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
                for i in range(len(locations)+rand.randint(1,3)):
                    thing =  self.roll(self.AppendixA['Dungeon Dressings'][key])
                contents.append(key + ': ' + thing)
            elif key == 'Specific' and room != 'Passage':
                things = []
                for kkey in self.AppendixA['Dungeon Dressings']['Specific'].keys():
                    for word in kkey.split(' '):
                        if room_purpose.find(word.lower()) > -1:
                            for i in range(len(locations)+rand.randint(1,3)):
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
    __slots__ = ('room_id', 'blocks','color', 'doors', 'is_exit', 'purpose', 'state', 'contents', 'parent', 'monster', 'treasure', 'furnishings', 'traps', 'hazards', 'hallway', 'stairs')

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

    def place_doors(self, number, trapped=False):
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
        temp = [border
                           for border in self.borders()
                           if not border.internal]
        for border in borders:
            x, y = border.position.point()

            if x == max_x:
                [temp.append(border) for _ in range(check_xy-max_x_num)]
            elif x == min_x:
                [temp.append(border) for _ in range(check_xy-min_x_num)]
            elif x >= mid_x-1 and x <= mid_x + 1 and y <= max_y-1 and y >= min_y+1:
                [temp.append(border) for _ in range(int(check_xy))]
            
            if y == max_y:
                [temp.append(border) for _ in range(check_xy-max_y_num)]
            elif y == min_y:
                [temp.append(border) for _ in range(check_xy-min_y_num)]
            
            elif y >= mid_y - 1 and y >= mid_y+1 and x <= max_x-1 and x >= min_x+1:
                [temp.append(border) for _ in range(int(check_xy))]

        
        if borders == []:
            borders = [border
                           for border in self.borders()
                           if not border.internal]
                          
        
        # make areas closest to the center more likely...
        
        
        neighbors = set()
        directions = set()
        attempts = 0

        while len(self.doors) < number and attempts < len(borders):
            border = random.sample(borders, 1)[0]
            check_position = border.position
            check_direction = border.direction
            okay = True
            
            if check_position in neighbors:  #borders an existing door
                okay = False
            elif len(list(directions)) < 4 and check_direction in directions:  #same wall...
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
        
        print('tpassage')
        start = self.blocks[0].position.point()
        for i in range(random.randint(9,12)):
            for j in range(8):
                if i <= 1 or j == 3 or j == 4:
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
                print('Dungeon Purpose Broken')
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
                self.monster = '{} [Motivation: {}]'.format(self.monster, self.parent.parent.roll_table(self.parent.parent.AppendixA['Monster Motivation']))
                
            if 'Hazard' in self.contents:
                self.hazards = self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Hazards'])
                
            if 'Obstacle' in self.contents:
                self.hazards = self.parent.parent.roll_table(self.parent.parent.AppendixA['Obstacles'])
            
            if 'Trap' in self.contents:
                self.traps = 'Trap({}):{} [Trigger: {}]'.format(self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Damage Severity'])
                                                             , self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Effects'])
                                                             , self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Traps']['Trap Trigger']))
            if 'Trick' in self.contents:
                tobj = self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Tricks']['Trick Objects'])
                self.traps = 'Trick {}: {}'.format(tobj, self.parent.parent.roll_table(self.parent.parent.AppendixA['Random Tricks']['Tricks']))
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
            if 'General' in key and self.hallway == False and self.stairs == None:
                for i in range(random.randint(1,len(self.doors)+1)):
                    self.furnishings.append('{}: {}'.format(key, self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Dressings'][key])))
            if key == 'Specific':
                for skey in self.parent.parent.AppendixA['Dungeon Dressings'][key]:
                    for a in skey.split(' '):
                        if a.lower() in self.purpose.lower():
                            self.furnishings.append('{}: {}'.format('General Furnishings and Appointments', self.parent.parent.roll_table(self.parent.parent.AppendixA['Dungeon Dressings'][key][skey])))
                                         
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

    def create_room(self, blocks, doors, trap=False, is_exit=True):
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

        room.place_doors(doors)
        
        return room
       
    def door_borders(self):
        for room in self.rooms:
            for border in room.door_borders():
                if not border.used:
                    yield border
                    
    def is_intersect_room(self, room):
        return any(current_room.is_intersect(room) for current_room in self.rooms)

    def room_positions_bruteforce(self, max_intersection_radius, new_room, dungeon_positions):
        
        filled_cells = {position.point() for position in dungeon_positions}


        for max_distance in range(0, max_intersection_radius):
            print(max_distance)
            #for dungeon_door in self.door_borders():
            for i, dungeon_door_object in enumerate(self.get_free_doors()):            
                dungeon_door = dungeon_door_object.borders[0]
                max_distance, dungeon_door, new_room_door, x, y = self.room_position_from_door(max_distance, new_room, dungeon_positions, dungeon_door)
                if max_distance != -1:
                    print('Good')
                    print(max_distance, dungeon_door, new_room_door, x, y)
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
                        print(dungeon_door.direction, new_room_door.direction, 'DING')
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
            
            door = self.get_free_doors()[0]  #radiate out from oldest doors
            dungeon_door = door.borders[0]
            max_distance, dungeon_door, new_room_door, x, y = self.room_position_from_door(max_intersection_radius,
                                                                                                  new_room,
                                                                                                  dungeon_positions,
                                                                                                  dungeon_door)
            try:                                                                                      
                dungeon_door_out_position = dungeon_door.mirror().position
                new_room_door_out_position = new_room_door.mirror().position

                filled_positions = dungeon_positions | new_room.block_positions()
            except AttributeError:
                return False
                
            try:
                path_length, corridor_path = find_path(dungeon_door_out_position,
                                                       new_room_door_out_position,
                                                       filled_cells=filled_positions,
                                                       max_path_length=max_distance)
            except IndexError:
                return False

            if path_length is None:
                return False

            # door is free and the positions are opposed      
            try:
                if len(dungeon_door.door.borders) < 2 and dungeon_door.is_mirrored(new_room_door) and len(new_room_door.door.borders) < 2:
                    # we're good...
                    door = dungeon_door.door
                    new_room.doors.pop(new_room.doors.index(new_room_door.door))
                    door.borders.append(new_room_door)
                    self.rooms.append(new_room)
                    new_room.doors.append(door)

                    new_corridor = Corridor(dungeon_door, new_room_door, corridor_path)

                    self.corridors.append(new_corridor)
                    
                    return True
                else:
                    return False
            except:
                if dungeon_door != None:
                    self.remove_door(dungeon_door)
                try:
                    del new_room_door
                except:
                    print()
                try:
                    del new_room
                except:
                    print()
                return False
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
            print('starting room exit',check)
                  
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
        return list(set(doors))
    
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
        while free_doors >= 1 and room_added == False:
            tries += 1
            free_doors = self.check_free_doors()
            if tries > 10:
                print(tries, free_doors, room_added)
            exit_chance = 95-self.info['level'] - int(len(self.rooms)/10)
            if exit_chance > 100:
                exit_chance = 100
            if random.randint(1,100) >= exit_chance:
                ## EXIT
                new_room = self.create_room(0,1,is_exit=True)
            else:
                d20 = random.randint(1,20)
                print('d20', d20)
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
            if stairs:
                # stair code...
                new_levels = []
                room_added = False
                new_room = self.create_rectangle_room(10,10,1)
                nd20 = random.randint(1,20)

                if nd20 <= 12 or nd20 == 16 or nd20 == 18:
                    # Down one level to a chamber
                    nlevel, check = self.check_level(-1)
                elif nd20 >= 13 and nd20 <= 15 or nd20 == 17 or nd20 >= 19:
                    #	Up one level to a chamber
                    nlevel, check = self.check_level(1)
                print('stair check',nd20, nlevel,check)
                if check:
                    mirror_room = Room(self, stairs=new_room)
                    mirror_room.color = new_room.color
                    mirror_room.blocks = []
                    if self.expand(new_room):
                        for block in new_room.blocks:
                            x, y = block.position.point()
                            new_block = Block(Position(x, y))
                            for nblock in mirror_room.blocks:
                                nblock.sync_borders_with(new_block)
                            mirror_room.blocks.append(new_block)
                        mirror_room.place_doors(1)
                        room_added = self.parent.levels[nlevel].expand(mirror_room, stairway=True)
                        if room_added == False:
                            self.rooms.pop(new_room)
                        else:
                            new_room.stairs = mirror_room
                            new_room.clear_room(True)
                            new_room.stock_room()
            else:
                    room_added = self.expand(new_room)
            if tries > 10:
                try:
                    self.remove_door(self.get_free_doors()[0])
                except IndexError:
                    print('Free Doors', self.check_free_doors())
                free_doors = self.check_free_doors()
            self.connect_free_doors(max_distance=3)
            