import os
import json
import pickle
import base64
import openai
import requests
import pandas as pd
import random as rand


class AIMegaDungeon:
    def __init__(self, filename=None, levels='levels.csv', keys='|'):
        '''
        map -> a dictionary that stores x, y, z coordinates as roughly 30ft. blocks... 0,0,0 being the dungeon entrance.  
        Stores the room id at that location.  Checked to see if something exists there.  Each room/passage takes up one
        (or more) blocks

        rooms -> room information, key is room id

        levels -> level information, key is z coordinate (0 for first level)

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
            self.levels = pd.read_csv(self.file_path(levels), sep='\t')
            new = 1
        if new == 0: # need a new instance
            self.filename = input('Name this dungeon:')
            self.map = {}
            self.rooms = {}
            self.levels = pd.read_csv(self.file_path(levels), sep='\t')
            self.Current_Orientation, self.Current_Room, self.Current_Location = None, None, None
            self.doors = {}
            self.locations = {}
            
            
            with open(self.file_path('AppendixA.pickle'), 'rb') as file:   
                self.AppendixA = pickle.load(file)
            print('Dungeon {} Created'.format(filename))

            if self.Current_Location == None:
                #self.start()
                print('start here?')
            else:
                print('INSERT A LOAD ROOM HERE')
            #self.save(filename)
            
  
    ## ADMIN FUNCTIONS
    def file_path(self, filename):
        return os.path.join(self.current_dir, '{}'.format(filename))
        
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
    def get_chat_response(self, prompt, model="gpt-3.5-turbo"):
        client = openai.OpenAI(api_key=self.OPENAI_API_KEY) # Create an OpenAI client instance
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
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
        """
        Build a GPT-5-mini prompt that strictly enforces floor dimensions.
        """

        wall_spaces_ft = 10

        
        dir_dct = {'south':'bottom','north':'top','east':'right side','west':'left side'}
        doors_text = "\n"
        dct_door_stuff = {'north':floor_h, 'south':floor_h, 'east': floor_w, 'west':floor_w}
        floor_ratio = get_image_ratio(self,[floor_w, floor_h])
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
                    print(f"Door on {d['wall']} wall spans x={door_x_start} to x={door_x_end}, y={y}")
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

        print(fx1, fx2, fy2, fy2)
        #WALL coordinates
        ndiffx = (floor_width + int(wall_spaces_ft/5))/2
        ndiffy = (floor_height + int(wall_spaces_ft/5))/2
        wx1 = int(squares/2) - ndiffx
        wx2 = int(squares/2) + ndiffx
        wy1 = int(squares/2) - ndiffy
        wy2 = int(squares/2) + ndiffy
        print(wx1, wx2, wy2, wy2)
        
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
        
        prompt = f"""***REALISTIC TOP-DOWN ORTHOGRAPHIC BATTLEMAP WITH VISUAL WALLS - {room_shape_main.upper()} {room_theme.upper()} {art_note_1.upper()}***

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
        """
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
        self.rooms[room_id]['image result'] = result
        
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
                
        print(f"Saved generated image to: {output_path}")
    
       
    ## MATH & WORKERS       
    def shift_from_wall(self, pos, facing, wall):
        """
        pos: (ew, ns, ud)
        facing: 'n', 's', 'e', 'w'
        wall: one of
            'Wall opposite entrance',
            'Same wall as entrance',
            'Wall left of entrance',
            'Wall right of entrance'
        """
    
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
        """
        Makes doors, rolls for room, finds exits, etc.
        """
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
       
        return room_desc, room_purpose, locations, room_id, dimensions

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
        print(divs)
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
                        print(door)
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
            print('Scale:',scale)

        # generate the prompt
        prompt = build_battlemap_prompt(self, canvas_w = canvas_w
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
                                                   , debug = True)
     
        file_name = self.file_path('{} room {}.png'.format(self.filename, room_id))
        self.render_image(room_id, file_name, prompt, model="openai/gpt-5-image-mini")
        
        
    ### Movement
