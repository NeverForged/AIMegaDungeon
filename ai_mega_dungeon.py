import os
import pickle
import base64
import openai
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
        self.OPENROUTER_API_KEY = keys.split('|')[0]
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

    def get_image(self, prompt, filename, model="dall-e-3"):
        client = openai.OpenAI(api_key=self.OPENAI_API_KEY) # Create an OpenAI client instance
        result = client.images.generate(
            model=model,
            prompt=prompt
        )
        
        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        # Save the image to a file
        with open(filename, "wb") as f:
            f.write(image_bytes)
            
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

    ### Initialization
    def new_door(self, door_location, exit=False, passage = False):
        '''
        
        '''
        
        tup, wall = self.shift_from_wall(self.Current_Location, self.Current_Orientation, door_location)
        coord = str(tuple(sorted([self.Current_Location, tup])))
        
        # if we already have the doors, ignore the request
        if coord not in self.doors.keys():
            self.doors[coord] = {}
            self.doors[coord]['exit'] = exit
            if passage == True:
                width = sorted((self.roll(self.AppendixA['Passage Width']), self.roll(self.AppendixA['Passage Width'])))[0]
                self.doors[coord]['door type'] = '{} passage leading 10ft. into darkness'.format(width)
            else:
                self.doors[coord]['door type'] = self.roll(self.AppendixA['Door Type'])
            
    def new_room(self, room='Chamber', start=False):
    '''
    Makes doors, rolls for room, finds exits, etc.
    '''
    
    try:
        room_id = max(list(self.rooms.keys())) + 1
    except:
        room_id = 0
        start = True
    if room=='Chamber':  # Chamber
        okay = False
        while okay == False:
            room_desc = self.roll(self.AppendixA['Chamber'])
            room_purpose = self.roll(self.AppendixA['Purpose'][self.levels[self.levels['level'] == self.Current_Location[2]]['purpose'].values[0]])

            print(room_desc)
            #Get the dimensions of the room
            if room_desc.find('Circle') > -1:
                dimensions = [room_desc[8:10], room_desc[8:10]]
            else:
                dimensions = room_desc[room_desc.find('×')-3:room_desc.find('×')+4].split(' × ')
            print(dimensions)
            # see if it fits in the map...
            locations = []
            locations.append(self.Current_Location)
            okay = True
            if int(dimensions[1])>40:
                check_loc = self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Wall opposite entrance')[0]
                if str(check_loc) in self.locations.keys():
                    okay = False
                else:
                    locations.append(check_loc)
            if int(dimensions[0])>40:
                check_loc = self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Wall right of entrance')[0]
                direction = 'right'
                if str(check_loc) in self.locations.keys():
                    check_loc = self.shift_from_wall(self.Current_Location, self.Current_Orientation, 'Wall left of entrance')[0]
                    direction = 'left'
                if str(check_loc) in self.locations.keys():
                    okay = False
                else:
                    locations.append(check_loc)
                    if int(dimensions[1])>40:
                        check_last = self.shift_from_wall(check_loc, self.Current_Orientation, 'Wall opposite entrance')[0]
                        if str(check_last) in self.locations.keys():
                            okay = False
                        else:
                            locations.append(check_last)
                            
        # mark these locations as this room
        for loc in locations:
            self.locations[str(loc)] = room_id
            print(loc)
        # Door Stuff Here...
        exit_key = room_desc[-1]
        room_desc = room_desc[:-1]
        exits = int(self.roll(self.AppendixA['Chamber_Exits_{}'.format(exit_key)]))
        if start==True and exits<4:
            exits = 4
        # first, find all the exits we already know about...
        doors = []
        for loc in locations:
            for key in self.doors.keys():
                if str(loc) in key:
                    doors.append(key)
        print(locations)
        print(doors)
        while len(doors) < int(exits): #need new doors...
            door_location = self.roll(self.AppendixA['Exit Location'])
            tup, wall = self.shift_from_wall(self.Current_Location, self.Current_Orientation, door_location)
            if tup in locations:
                self.current_location = tup
            self.new_door(door_location, exit=False, passage = False)
            doors = []
            for loc in locations:
                for key in self.doors.keys():
                    if str(loc) in key:
                        doors.append(key)
            print(len(doors), exits)
            
        make_room(self, room, room_purpose, locations, room_id)
        
    def make_room(self, room, room_purpose, locations, room_id):
        self.rooms[room_id] = {}
        self.rooms[room_id]['locations'] = locations
        self.rooms['shape'] = room
        self.rooms['purpose'] = room_purpose
        doors = []
        door_location = {'(0, -1, 0)' : 's',
                 '(0, 1, 0)' : 'n',
                 '(1, 0, 0)' : 'e',
                 '(-1, 0, 0)' : 'w'}
        for key in self.doors.keys():
            for loc in locations:
                if key.find(str(loc)) > -1:
                    door = self.doors[key]['door type']
                    if door.find('passage') == -1:
                        door = door + ' door'
                    if self.doors[key]['exit']:
                        door = door + ' that leads out of the dungeon'
                    dif = str(tuple([n-self.Current_Location[i] for i, n in enumerate([int(a) for a in key.replace(str(self.Current_Location),'').replace('(','').replace(')','').replace(' ','').split(',') if len(a) > 0])]))

                    if door.lower().find('secret') == -1:
                        doors.append(door + ' located on the {} wall'.format(door_location[dif]))
        walls = self.levels[self.levels['level'] == self.Current_Location[2]]['walls'].values[0]
        floors = self.levels[self.levels['level'] == self.Current_Location[2]]['floors'].values[0]
        ceilings = self.levels[self.levels['level'] == self.Current_Location[2]]['ceilings'].values[0]
        # check contents...
        contents = []
        for key in self.AppendixA['Dungeon Dressings'].keys():
            if key != 'General Furnishings and Appointments':
                thing =  self.roll(self.AppendixA['Dungeon Dressings'][key])
                contents.append(key + ': ' + thing)
            else:
                things = []
                for loc in locations:
                    things.append(self.roll(self.AppendixA['Dungeon Dressings'][key]))
                self.rooms[room_id][key] = things
                contents.append(key + ': ' + ', '.join(things))
                    
            
        query = prompt = """
                       Given the following:

                        '
                        Room Specification (draw exactly this):
                                Floor shape and size: {} 
                                Room purpose or theme: {}
                                Doors or passages: {}
                                Walls: {}
                                Floor: {}
                                Features (show visually only): {}
                                Ceilings (description only, not in art): {}
                        '
                        
                        
                        First, a short D&D room description like those found in blue boxes in old modules with no header
                        then, include the following character: "|"
                        Then provide a prompt optimized for openai/gpt-5-image-mini to draw the above given the following specifications.  
                        Be sure to calculate the size of the floor in pixels and add the additional area needed to represent the walls, an extra 140 pixels:
                        '
                         Grid Requirements:
                                Draw a 5-ft by 5-ft square grid covering only the floor. 
                                Each grid square must be exactly 70 by 70 pixels in the final image. 
                                Grid lines must appear as seams in the floor, and the squares must be 70px on a side. 
                                Grid lines must appear only on the floor and not on walls, doors, or any area outside the room.

                        Style and Rendering Rules:
                            North is the top of the image. 
                            Use a strict orthographic top-down view with a fisheye lens perspective showing the inner walls (like top down video games). 
                            Match classic D&D virtual tabletop battlemaps in full color. 
                            Walls and doors must be shown from above and aligned to the floor; south walls should appear upside down to show that they are right side up to someone in the room
                            Doors must follow the angle of the wall they are on and must never be drawn on the floor.
                            Passages must show only a short continuation beyond the doorway and then fade into darkness. 
                            Do not imply or show any additional rooms. 
                            Only show what would be visible from inside the room. 
                            Everything outside the room must be solid black. 
                            Do not include anything that is not explicitly specified.
            			    Doors should either be 52 px wide (single) or 104 px wide (stone or portcullis)
        		            Make sure the model includes every door and checks the dimensions and squares to make sure it matches the description above
                            '

                            
                        """.format(room, room_purpose,'\n'.join(doors),walls,floors,'\n'.join(contents),ceilings)

        chat_gpt = self.get_chat_response(prompt=str(query))
        lst = chat_gpt.split('|')
        blue_box = lst[0]
        room_image_prompt = lst[1]

        self.rooms[room_id]['blue box'] = blue_box
        # make room image...
        return room_image_prompt
   
    
    ### Movement
    def start(self):
        '''
        Starting a dungeon, making the first level and room...
        '''
        self.Current_Orientation = None
        while self.Current_Orientation not in ['n','s','e','w']:
            self.Current_Orientation = input('What Direction is the Entrance?')[:1].lower()
        self.Current_Room = 0
        self.Current_Location = (0,0,0)
        
        # set the new level... level 0

        ### roll for a starting location...
        room_inf = self.roll(self.AppendixA['Starting Area']).split(' | ')
        room = room_inf[0]
        for door in room_inf[1:]:
            a = door.split(', ')
            passage = False
            exit = False
            if a[0].find('passage')>-1:
                passage = True
            if a[1].lower().find('same')>-1:
                exit = True
            self.new_door(a[1], exit, passage)
        query = self.make_room(room, 'Gatehouse for the Dungeon')
        return query
