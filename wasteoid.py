# python/libtcod roguelike // WASTEOID
# remember to call libtcod for libtcod functions!
#from pybass import *
import libtcodpy as libtcod
import math
import textwrap

VERSION = '0.05a'

INTRO_MESSAGE = 'you descend into the garbage tunnels... the trash has shifted.'

#constants
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 60
#sizes and coordinates for GUI
BAR_WIDTH = 12
LOG_PANEL_HEIGHT = 10
LOG_PANEL_Y = SCREEN_HEIGHT - LOG_PANEL_HEIGHT
#size of map portion shown on-screen
CAMERA_WIDTH = SCREEN_WIDTH
CAMERA_HEIGHT = SCREEN_HEIGHT - LOG_PANEL_HEIGHT
#message bar constants
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 3
MSG_HEIGHT = LOG_PANEL_HEIGHT - 1
#inventory gui
INVENTORY_WIDTH = 50
#map initialization
MAP_WIDTH = SCREEN_WIDTH
MAP_HEIGHT = SCREEN_HEIGHT - LOG_PANEL_HEIGHT
#dungeon gen config
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 4
MAX_ROOMS = 25
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2
#intersections check - True allows for intersecting rooms
INTERSECTS = True
#fov - FOV_BASIC, DIAMOND, SHADOW, PERMISSIVE0-8, RESTRICTIVE
FOV_ALGO = 0 #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
#health regen constants
HEALTH_REGEN_RATE = 80 # amount of turns before health regenerates
HEALTH_REGEN_AMOUNT = 1 # amount health regens by
#damage strength multiplier
DAMAGE_STRENGTH_MULTIPLIER = 2.00 # defines the maximum influence strength has on dealt damage, in percentage.
#critical hits
CRIT_RATE = 4 # critical hit rate, in percentage.
CRIT_MULTIPLIER = 1.5 # critical hit multiplier - write percentage as decimals, ie 1.0 = 100%
GORE_KILL_THRESHOLD = 0.8 # percentage of max hp. damage dealt required to perform a gorekill.
#gorekills occur when you deal x percentage of damage BELOW 0 hp. 10hp means -8hp AT DEATH to perform gorekill.

#basic needs rates
HUNGER_RATE = 90 # 1 turn = 10 seconds. 90 turns is 15 minutes
THIRST_RATE = 60 # 1 turn = 10 seconds. 60 turns is 10 minutes
#hunger/thirst damage amounts
HUNGER_DAMAGE = 2
THIRST_DAMAGE = 4

#various effect constants
ZAP_RANGE = 5
ZAP_DAMAGE = 20
CONFUSE_RANGE = 20
CONFUSE_NUM_TURNS = 10

#inventory carry limit - implement strength-based system asap please
CARRY_LIMIT = 26

PLAYER_NAME = 'scavenger'
LIMIT_FPS = 12

#color definitions
color_dark_wall = libtcod.desaturated_red
color_lit_wall = libtcod.lighter_red
color_dark_ground = libtcod.dark_sepia
color_lit_ground = libtcod.light_sepia

#define functions and classes
class Rect:
	#a rectangle on the map. characterizes a room
	def __init__(self, x, y, w, h ):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
	
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
		
	def intersect(self, other):
		#returns true if this rectangle intersects with another
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
				self.y1 <= other.y2 and self.y2 >= other.y1)

class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		self.explored = False
		
		#by default, if a tile is blocked it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight

class Object:
	#generic object represented by an on-screen character - anything from players to stairs
	def __init__(self, x, y, char, name, color, blocks=False, fighter=None,
	ai=None, look=None, item=None, needs=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.fighter = fighter
		self.ai = ai
		self.look = look
		self.item = item
		self.needs = needs
		
		if self.fighter: #parents object to fighter
			self.fighter.owner = self
		
		if self.ai: #parents object to ai
			self.ai.owner = self
			
		if self.look: #parents object to looker
			self.look.owner = self
			
		if self.item: #parents object to item
			self.item.owner = self
			
		if self.needs: #parents object to needs
			self.needs.owner = self
				
	def move(self, dx, dy):
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		#normalize it to 1 length, preserving direction
		#then round it and convert to integer so movement is restricted to grid
		dx = int(round(dx / distance))
		dy = int(round(dy /distance ))
		self.move(dx, dy)
	
	def distance_to(self, other):
		#return distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx**2+dy**2)
	
	def draw(self):
		#only show if visible to player
		if(libtcod.map_is_in_fov(fov_map, self.x, self.y)):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
		
	def clear(self):
		#clears the character
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
		
	def send_to_back(self):
		#make this object be drawn first, so all others appear above it on same tile
		global objects
		objects.remove(self)
		objects.insert(0,self)

class Fighter:
	#combat related properties and methods ( players, monsters, npcs )
	def __init__(self, hp, defense, pow, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.pow = pow
		self.death_function = death_function
		
	def health_regen(self):
		global regen_timer
	
		if self.owner.needs:
			if self.owner.needs.thirst < self.owner.needs.max_thirst and self.owner.needs.hunger < self.owner.needs.max_hunger:
				if (self.hp < self.max_hp):
					if(regen_timer <= 0):
						self.heal(HEALTH_REGEN_AMOUNT)
						regen_timer = HEALTH_REGEN_RATE
					elif (regen_timer > 0):
						regen_timer -= 1

	def take_damage(self, damage):
		#apply damage, if possible
		if damage > 0:
			self.hp -= damage			
			#check for deaths and uses objects death_function (monster/player)
			if (self.hp <= 0):
				function = self.death_function
				if function is not None:
					function(self.owner)

	def heal(self,amount):
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp

	def attack(self, target):
		#attack strength formula
		attack_strength = libtcod.random_get_float(0,self.pow, self.pow * DAMAGE_STRENGTH_MULTIPLIER)
		attack_strength = int(round(attack_strength))
		#damage formula
		damage = attack_strength - target.fighter.defense
		#placeholder var
		random_message = False
		attack_message = ''
		
		if((damage) * CRIT_MULTIPLIER) > 0: #checks if the critical attack would do any damage at all.
			if(libtcod.random_get_int(0,0,100) < CRIT_RATE):
				#critical damage - occurence rate defined by CRIT_RATE, and extra damage defined by CRIT_MULTIPLIER. 
				#crit formula is - damage * crit_multi = damage - attack of 10 would do 22 on critical with 120% damage multiplier
				damage *= CRIT_MULTIPLIER # critical hit damage
				damage = int(round(damage)) + target.fighter.defense # rounds up to nearest integer and bypasses enemy defense
				message(self.owner.name + ' lands a critical hit!',libtcod.light_red)

		#DAMAGE MESSAGES - each level of severity ( every 25% of max HP ) has increasingly brutal flavor text.
		#each level has 4-5 different sentences, chosen at random.
		if damage > 0: #make the target take damage, if it actually hurts. otherwise you'd end up healing the enemy!
			#choose a random attack onomatopoeia
			random_onoma = libtcod.random_get_int(0,1,len(attack_onoma_msg)-1)
			onoma = attack_onoma_msg[random_onoma]
		
			#sets attack color to white, just in case
			attack_color = libtcod.white	
			# attack_0_10_msg - messages for damage of 0-24% of max HP
			if (damage < ( 0.1 * target.fighter.max_hp )):
				random_message = libtcod.random_get_int(0,0,len(attack_0_10_msg)-1)
				attack_message = attack_0_10_msg[random_message]
				attack_color = libtcod.lightest_red
			# attack_10_35_msg - messages for damage of 25-49% of max HP
			elif (damage >= (0.1 * target.fighter.max_hp) and damage < (0.35 * target.fighter.max_hp) ):
				random_message = libtcod.random_get_int(0,0,len(attack_10_35_msg)-1)
				attack_message = attack_10_35_msg[random_message]
				attack_color = libtcod.lighter_red
			# attack_35_65_msg - messages for damage of 50-74% of max HP
			elif (damage >= (0.35 * target.fighter.max_hp) and damage < (0.65 * target.fighter.max_hp) ):
				random_message = libtcod.random_get_int(0,0,len(attack_35_65_msg)-1)
				attack_message = attack_35_65_msg[random_message]
				attack_color = libtcod.light_red
			# attack_65_85_msg - messages for damage of 75-85% of max HP
			elif (damage >= (0.65 * target.fighter.max_hp) and damage < (0.85 * target.fighter.max_hp)):
				random_message = libtcod.random_get_int(0,0,len(attack_65_85_msg)-1)
				attack_message = attack_65_85_msg[random_message]
				attack_color = libtcod.red
			# attack_85_100_msg - messages for damage of 85%+ of max HP
			elif (damage >= (0.85 * target.fighter.max_hp)):
				random_message = libtcod.random_get_int(0,0,len(attack_85_100_msg)-1)
				attack_message = attack_85_100_msg[random_message]
				attack_color = libtcod.dark_red
					
			message(onoma+'! '+self.owner.name + ' ' + attack_message + ' ' + target.name + ' for ' + str(damage) + ' hitpoints.', attack_color)
			
			target.fighter.take_damage(damage)
			attack_onoma_msg.remove(onoma)
			attack_onoma_msg.insert(0,onoma)
		else:
			message(self.owner.name + ' feebly pokes ' + target.name + '.')

class BasicMonster:
	#basic monster AI
	def take_turn(self):
		#basic monster takes its turn. if you can see it, it will chase you. 
		#currently stops out of FoV, change this soon
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			#message('the ' + monster.name + ' spots you!', libtcod.red)
			#move monster towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

class ConfusedMonster:
	#AI for confused monster
	def __init__(self,old_ai,num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	
	def take_turn(self):
		if self.num_turns > 0: #still confused
			#move in a random direction
			self.owner.move(libtcod.random_get_int(0,-1,1),libtcod.random_get_int(0,-1,1))
			self.num_turns -= 1		
		else: #restore previous ai and delete current (confused) ai
			self.owner.ai = self.old_ai
			message(self.owner.name+' snapped out of it!',libtcod.light_green)

class Looker:
	global game_state
	#player-only Object component. used for the various targeting uses.
	#returns a list of names under the current tile of the looker
	def get_names(self,x=None,y=None):
		
		#checks for objects names at the x and y coords of the looker, as long as it's in FOV
		names = [obj.name for obj in objects
			if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map,obj.x,obj.y)]
		
		#checks for object names in FOV
		#names = [obj.name for obj in objects
		#	if obj.name != PLAYER_NAME and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
		if not names:
			names='nothing'
		else:
			names = ', '.join(names)
		return names
		
	def walk_names(self):
		#prints names when walking over objects
		self.owner = player		
		names = [obj.name for obj in objects
			if obj.x == self.owner.x and obj.y == self.owner.y and obj.name != PLAYER_NAME]
		if (len(names) > 1):
			return 'there are several items here.'
		elif(len(names) == 1):
			return('you stand over '+''.join(names))

class Item:
	#item class - items are picked up and used
	def  __init__(self,use_function=None, secondary_function=None, effect_amount=None,
	secondary_effect_amount=None, effect_quality=None, effect_radius=None):
		#effect amount is how much of an effect an item should have. f.ex healing amount for health potions, damage value for single-use weapons, etc
		self.use_function = use_function
		self.secondary_function = secondary_function
		self.effect_amount = effect_amount
		self.secondary_effect_amount = secondary_effect_amount
		self.effect_quality = effect_quality
		self.effect_radius = effect_radius
		
		if(self.effect_amount): #sets self.amount to specified amount, 1 if attribute is missing
			self.amount = self.effect_amount
		else:
			self.amount = 1
		if(self.secondary_effect_amount): #secondary use_function effect amount.
			self.secondary_amount = secondary_effect_amount
		else:
			self.secondary_amount = 1
		if self.effect_radius: #sets effect radius for primary use function
			self.effect_radius = effect_radius
		else:
			self.effect_radius = 1
		
	def use(self):
		#generic function. calls item's use_function, if it is defined
		if self.use_function is None:
			message('you can\'t use the '+self.owner.name+' for anything.')
		else:
			if self.use_function(self.amount, self.owner.name, is_primary=True, quality=self.effect_quality, 
			effect_radius=self.effect_radius) != 'cancelled':
				if self.secondary_function:
				#if the item has a secondary use function, use it.
					self.secondary_function(self.secondary_amount)
				inventory.remove(self.owner) #destroys after use, unless it was cancelled
	
	def drop(self):
		#removes from player inventory and adds to map at players coords
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.send_to_back()
		self.owner.x = player.x
		self.owner.y = player.y
		message('you dropped the '+self.owner.name+'.',libtcod.yellow)
		
	def pick_up(self):
		#add to players inventory and remove from map
		if len(inventory) >= CARRY_LIMIT:
			message('can\'t pick up any more junk. you let the '+self.owner.name+' go.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			
			random_prefix = libtcod.random_get_int(0,1,len(pickup_prefix_msg)-1)
			prefix = pickup_prefix_msg[random_prefix]
			
			message(prefix+'! snatched the '+self.owner.name+'!',libtcod.green)
			pickup_prefix_msg.remove(prefix)
			pickup_prefix_msg.insert(0,prefix)

class Needs:
	#basic needs. hunger and thirst gets managed here
	def __init__(self,hunger,thirst):
		self.max_hunger = hunger
		self.hunger = hunger - hunger
		self.max_thirst = thirst
		self.thirst = thirst - thirst
		
	def hunger_increase(self):
		#increases hunger
		global hunger_timer
		
		if (self.hunger < self.max_hunger):
			if(hunger_timer <= 0):
				self.hunger += 1
				hunger_timer = HUNGER_RATE
				if(self.hunger == int(round(self.max_hunger * 0.35))):
					message('your stomach growls. eat something.', libtcod.grey)
			elif(hunger_timer > 0):
				hunger_timer -= 1

		elif(self.hunger == self.max_hunger):
			if(hunger_timer <= 0):
				message('you\'re hurt by starvation!', libtcod.dark_red)
				self.owner.fighter.take_damage(HUNGER_DAMAGE)
				hunger_timer = HUNGER_RATE
			elif(hunger_timer > 0):
				hunger_timer -= 1
	
	def thirst_increase(self):
		#increases thirst
		global thirst_timer
		
		if(self.thirst < self.max_thirst):
			if(thirst_timer > 0):
				thirst_timer -= 1
			elif(thirst_timer <= 0):
				self.thirst += 1
				thirst_timer = THIRST_RATE
				if(self.thirst == int(round(self.max_thirst * 0.35))):
					message('you\'ve got cottonmouth. drink something.', libtcod.grey)
		elif(self.thirst == self.max_thirst):
			if thirst_timer > 0:
				thirst_timer -= 1
			elif thirst_timer <= self.max_thirst:
				message('you\'re hurt by dehydration!', libtcod.dark_red)
				self.owner.fighter.take_damage(THIRST_DAMAGE)
				hunger_timer = THIRST_RATE			
				
	def satiate(self,amount):
		self.hunger -= amount
		if(self.hunger <= 0):
			self.hunger = 0
			
	def quench(self,amount):
		self.thirst -= amount
		if(self.thirst <= 0):
			self.thirst = 0

def handle_keys():
	#checks if an item was picked up
	picked_up = False

	#key input and exit handling
	key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED) #turnbased
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#alt-enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'esc' #exit game
	elif key.vk == libtcod.KEY_ENTER:
		return 'enter-key'
	
	if(game_state == 'playing'):
		#PHYSICAL KEYS
		#movement keys
		if (key.vk == libtcod.KEY_UP) or (key.c == ord('k')) or (key.vk == libtcod.KEY_KP8):
			return player_move_or_attack(0,-1)
		elif (key.vk == libtcod.KEY_DOWN) or (key.c == ord('j')) or (key.vk == libtcod.KEY_KP2):
			return player_move_or_attack(0,1)
		elif (key.vk == libtcod.KEY_LEFT) or (key.c == ord('h')) or (key.vk == libtcod.KEY_KP4):
			return player_move_or_attack(-1,0)
		elif (key.vk == libtcod.KEY_RIGHT) or (key.c == ord('l')) or (key.vk == libtcod.KEY_KP6):
			return player_move_or_attack(1,0)
		#diagonal movements
		elif (key.vk == libtcod.KEY_KP7):#up-left
			return player_move_or_attack(-1,-1)
		elif (key.vk == libtcod.KEY_KP9):#up-right
			return player_move_or_attack(1,-1)
		elif (key.vk == libtcod.KEY_KP1):#down-left
			return player_move_or_attack(-1,1)
		elif (key.vk == libtcod.KEY_KP3):#down-right
			return player_move_or_attack(1,1)
			
		#CHARACTER KEYS
		elif (key.c == ord('.')) or (key.vk == libtcod.KEY_KP5 ):
		#wait a turn
			return 'wait'
				
		elif (key.c == ord('x')):
		#look around you
			message('you look around and see ' + player.look.get_names())
			return 'no-move'
			
		elif (key.c == ord('g')):
		#get/pick up an item
			for object in objects: #looks for item in players tile
				if object.x == player.x and object.y == player.y and object.item:
					object.item.pick_up()
					picked_up = True
					break
			if picked_up:
				return 'grab'
			else:
				return 'no-move'
		#INVENTORY KEYS
		elif (key.c == ord('i')):
			#shows inventory
			chosen_item = inventory_menu('junk. nothing but junk.\n')
			if chosen_item is not None:
				chosen_item.use()
			else:
				return 'no-move'
		elif (key.c == ord('d')):
			#drops an item
			chosen_item = inventory_menu('choose an item to drop')
			if chosen_item is not None:
				chosen_item.drop()
				return 'drop'
			else:
				return 'no-move'
		elif (key.c == ord('a')):
			#uses an item
				chosen_item = inventory_menu('use an item')
				if chosen_item is not None:
					chosen_item.use()
					return 'use'
				else:
					return 'no-move'
		#no keys are pressed? no turn was used!
		else:
			return 'no-move'

def is_blocked(x,y):
	global map
	#checks current map tile
	if map[x][y].blocked:
		return True
	#checks for blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
	
	return False #if two previous statements fail, the tile is not blocked

def player_move_or_attack(dx,dy):
	global fov_recompute
	#move/attack coords
	x = player.x + dx
	y = player.y + dy		
	
	#looks for attackable objects
	target = None
	for object in objects:
		if (object.fighter and object.x == x and object.y == y):
			target = object
			break
			
	if target is not None:
		player.fighter.attack(target)
	else:
		if not map[x][y].blocked:
			player.move(dx,dy)
			fov_recompute = True
			return 'player-move'
		else:
			message('you bump into the wall',libtcod.light_grey)
			return 'no-move'

def player_death(player):
	#the game is end!
	global game_state
	game_state = 'dead'
	message('you\'re dead!',libtcod.dark_red)
	#for added effect, changes the player character to a corpse
	player.char = '%'
	player.color = libtcod.lightest_grey

def monster_death(monster):
	#turns the enemy into a corpse.
	#doesn't block or move, can't attack or be attacked
	#to check violent death, hp at death must exceed given % of max_hp, ie -3 damage on 10 mhp
	violence_limit = monster.fighter.max_hp * GORE_KILL_THRESHOLD
	if(monster.fighter.hp <= -violence_limit):
		message('the ' + monster.name + '\'s head bursts open with a sickening crack!',libtcod.dark_red)
	else:
		message(monster.name + ' was killed!',libtcod.light_red)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'bloody remains of a ' + monster.name
	monster.send_to_back()
	
	#turns corpse into an item that can be picked up
	item_component = Item(use_function=satiate_effect, effect_amount=5,
	secondary_function=quench_effect, secondary_effect_amount=-1, effect_quality = 'disgusting')
	monster.item = item_component
	monster.item.owner = monster

def make_map():
	global map, player
	
	#fill map with "blocked" tiles
	map = [[ Tile(blocked=True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		#random width and height
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#random position without going out of bounds
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
		
		new_room = Rect(x,y,w,h)
		#run through existing rooms to see if intersection occurs
		failed = False
		if INTERSECTS == False: #should the intersect check occur?
			for other_room in rooms:
				if new_room.intersect(other_room):
					failed = True
					break
				
		if not failed:
			#no intersections, valid room!
			create_room(new_room)
			#center coords of new room
			(new_x, new_y) = new_room.center()
			
			#ROOM GEN ROOM ORDER / COMMENT OUT
			#room_no = Object(new_x, new_y, chr(65+num_rooms), libtcod.white)
			#objects.insert(0, room_no) #renders early to show enemies
				
			if num_rooms == 0:
				#first room, player spawn.
				player.x = new_x
				player.y = new_y
			else:
				#all rooms after first get connected to previous room with a tunnel
				#center coords of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				#rooms can be connected either horizontally, then vertically, or vice versa
				#both are equally valid, so lets do a variation to make the map a little more interesting!
				if libtcod.random_get_int(0,0,1) == 1:
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
			#places objects AFTER the player
			place_objects(new_room)
			#append the new room to the list
			rooms.append(new_room)
			num_rooms += 1

def fov_init():
	global fov_map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

def create_room(room):
		global map
		#go through the tiles in the rectangle and make them passable
		for x in range(room.x1 +1, room.x2):
			for y in range(room.y1 +1, room.y2):
				map[x][y].blocked = False
				map[x][y].block_sight = False

def create_h_tunnel(x1,x2,y):
	global map
	for x in range(min(x1,x2), max(x1,x2)+1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def create_v_tunnel(y1,y2,x):
	global map
	for y in range(min(y1,y2), max(y1,y2)+1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def place_objects(room):
	global map
	#choose random amount of monsters
	num_monsters = libtcod.random_get_int(0,0, MAX_ROOM_MONSTERS)
	#places monsters in rooms, according to max monsters
	for i in range(num_monsters):
		#choose a random spot in the room
		#-/+1 avoids monsters spawning in walls
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		if not is_blocked(x,y):
			choice = libtcod.random_get_int(0,0,100)#rolls from 0-100
			if choice <= 30: #30% chance to spawn giant scorpion 'S'
				fighter_component = Fighter(hp=12, defense=4, pow=3, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x,y,'S', 'giant scorpion', libtcod.red, blocks=True,
				fighter=fighter_component, ai=ai_component)
			elif choice > 30 and choice <= 50: #20% chance
				fighter_component = Fighter(hp=8, defense=3, pow=1, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x,y,'s', 'irradiated snail', libtcod.green, blocks=True,
				fighter = fighter_component, ai = ai_component)
			else:
				fighter_component = Fighter(hp=6, defense=2, pow=2, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x,y,'f', 'mutated fish', libtcod.dark_green, blocks=True,
				fighter=fighter_component, ai=ai_component)
			
			objects.append(monster)
		
	#chooses random amount of items
	num_items = libtcod.random_get_int(0,0, MAX_ROOM_ITEMS)
	#places items in rooms, according to max items
	for i in range(num_items):
		x = libtcod.random_get_int(0,room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0,room.y1+1, room.y2-1)
		
		if not is_blocked(x,y):
			choice = libtcod.random_get_int(0,0,100)
			if choice < 20:
				#HEALTH POTION
				item_component = Item(use_function=heal_effect, effect_amount=10, 
				secondary_function=quench_effect, secondary_effect_amount=2)
				item = Object(x,y,'i','health potion', libtcod.dark_red, item=item_component)
				objects.append(item)
				item.send_to_back() # item appears below player/monsters
			elif choice >= 20 and choice < 30:
				#AUTO TASER
				item_component = Item(use_function=zap_effect, effect_amount=20, effect_quality=1)
				item = Object(x,y,'t','automatic taser', libtcod.cyan, item=item_component)
				objects.append(item)
				item.send_to_back()
			elif choice >= 30 and choice < 40:
				#SMALL BOTTLE OF WATER
				item_component = Item(use_function=quench_effect, effect_amount=20)
				item = Object(x,y,'i', 'small plastic bottle of water', libtcod.blue, item=item_component)
				objects.append(item)
				item.send_to_back()
			elif choice >= 40 and choice < 55:
				#LASER POINTER
				item_component = Item(use_function=confuse_effect, effect_amount=10, effect_quality=20)
				item = Object(x,y,'|', 'laser pointer', libtcod.gold, item=item_component)
				objects.append(item)
				item.send_to_back()

def render_all():
	global fov_map, color_dark_wall, color_lit_wall
	global color_dark_floor, color_lit_floor
	global fov_recompute
		
	if fov_recompute:
		#recompute FOV is needed ( after player movement etc )
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
			
		render_map()
	
	#draw all objects in the list
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
	#blits content of offscreen console to root console
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
	#prepare to render the gui log panel
	libtcod.console_set_default_background(log_panel, libtcod.black)
	libtcod.console_clear(log_panel)

	print_msg_log()

	#PLAYER STAT BARS
	#HP
	render_bar(1,3,BAR_WIDTH,log_panel,"BLOOD", player.fighter.hp, 
		player.fighter.max_hp, libtcod.darker_red, libtcod.darkest_red)
	#HUNGER
	render_bar(1,5,BAR_WIDTH,log_panel,'HNGR', player.needs.hunger, 
	player.needs.max_hunger, libtcod.grey, libtcod.desaturated_red)
	#THIRST
	render_bar(1,7,BAR_WIDTH,log_panel,'THRST',player.needs.thirst,
	player.needs.max_thirst, libtcod.light_blue, libtcod.desaturated_blue)
	#blit the contents of log panel to root console
	libtcod.console_blit(log_panel,0,0,SCREEN_WIDTH,LOG_PANEL_HEIGHT,0,0,LOG_PANEL_Y)

def render_map():
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			wall = map[x][y].block_sight
			visible = libtcod.map_is_in_fov(fov_map, x, y)
			
			if not visible:
				if map[x][y].explored:
					if wall:
						libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
			else:
				if wall:
					libtcod.console_set_char_background(con, x, y, color_lit_wall, libtcod.BKGND_SET)
				else:
					libtcod.console_set_char_background(con, x, y, color_lit_ground, libtcod.BKGND_SET)
				map[x][y].explored = True

def render_bar(x,y, total_width, panel, name, value, maximum, bar_color, back_color):
	#render a status bar for hp/survival rates/etc. first calculate width
	bar_width = int(float(value) / maximum * total_width)
	
	#renders background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel,x,y,total_width,1,False, libtcod.BKGND_SET)
	#then renders the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel,x,y, bar_width,1,False, libtcod.BKGND_SET)
		
	#aligned descriptive text with values
	libtcod.console_set_default_foreground(panel,libtcod.white)
	libtcod.console_print_ex(panel, x+total_width-1 , y, libtcod.BKGND_NONE, libtcod.RIGHT,
		name + ': ' + str(value) + '/' + str(maximum))

def print_msg_log():
	#print messages, one line at a time
	y = 1
	for (line,color) in game_msgs:
		libtcod.console_set_default_foreground(log_panel,color)
		libtcod.console_print_ex(log_panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1

def clear_all():
	for object in objects:
		object.clear()

def message(new_msg,color = libtcod.white, i=0):
	#split the message to different lines if necessary
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		#add the new line as a tuple with text and color
		game_msgs.append( (line.upper(), color) )

def menu(header, options, width):
	#generic menu function. has automatic height calculation 
	if len(options) > CARRY_LIMIT: raise ValueError('Cannot have a menu with more than'+str(CARRY_LIMIT)+'options.')
	#calculates total height, one line per option
	header_height = libtcod.console_get_height_rect(con,0,0,width,SCREEN_HEIGHT,header)
	height = len(options) + header_height
	#creates an off-screen console, menu window
	window = libtcod.console_new(width,height)
	#prints header, words wrapped
	libtcod.console_set_default_foreground(window,libtcod.white)
	libtcod.console_print_rect_ex(window,0,0,width,height,libtcod.BKGND_NONE,libtcod.LEFT, header)
	#prints options
	y = header_height
	letter_index = ord('a') #gets ascii code from a character
	for option_text in options:
		text = chr(letter_index)+') ' + option_text
		libtcod.console_print_ex(window,0,y,libtcod.BKGND_NONE,libtcod.LEFT,text)
		y += 1
		letter_index += 1
	#blits content of window console to root console/screen
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window,0,0,width,height,0,x,y,1.0,0.7)
	#shows root console
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None

def inventory_menu(header):
	#show a menu with each item of the inventory as an option
	if len(inventory) == 0:
		options = ['no junk!\n']
	else:
		options = [item.name for item in inventory]

	index = menu(header,options,INVENTORY_WIDTH) #stores index value from menu
	#if an item was chosen, return its index value
	if index is None or len(inventory) == 0: return None
	else: return inventory[index].item

def closest_monster(max_range):
	#find closest enemy up to a maximum range, and in the players fov
	closest_enemy = None
	closest_dist = max_range+1 # not quite sure why +1 but what the heck
	
	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calculate distance between player and monsters in FOV
			dist = player.distance_to(object)
			if dist < closest_dist:
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def target_tile(max_range=None):
	#
	print 'target-tile'

def heal_effect(amount, name=None, quality=None, is_primary=False, effect_radius=1):
	#heals the player by specified amount
	if not name:
		name = 'medicine'
	if not quality:
		quality = 'feels good'

	if player.fighter.hp == player.fighter.max_hp:
		message('already at full health!', libtcod.desaturated_red)
		return 'cancelled'
	else:
		player.fighter.heal(amount)
		if is_primary:
			message('you consume the '+name+'. '+quality+'.', libtcod.green)
		
def satiate_effect(amount, name=None, quality=None, is_primary=False, effect_radius=1):
	#satiates player hunger by specified amount
	if not quality:
		quality = 'very bland'
	if not name:
		name = 'food'
	
	if player.needs.hunger <= 0:
		message('you aren\'t hungry.')
		return 'cancelled'
	else:
		player.needs.satiate(amount)
		if is_primary:
			message('you eat the '+name+'. it was '+quality+'.', libtcod.light_green)
		if amount < 0:
			message('you feel a little hungrier after that.',libtcod.light_grey)
		
def quench_effect(amount, name=None, quality=None, is_primary=False, effect_radius=1):
	#quenches players thirst by specified amount
	if not name:
		name = 'liquid'
	if not quality:
		quality = 'very bland'
	
	if player.needs.thirst <= 0 and is_primary:
		message('you aren\'t thirsty.')
		return 'cancelled'
	else:
		player.needs.quench(amount)
		if is_primary:
			message('you drink the '+name+'.', libtcod.light_blue)
		if amount < 0:
			message('your mouth feels drier after that.', libtcod.light_grey)

def zap_effect(amount, name=None, quality=None, is_primary=False, effect_radius=1):
	#finds closest enemy and zaps it
	if not name:
		name = 'device'
	if not quality:
		quality = ZAP_RANGE
	if not amount:
		amount = ZAP_DAMAGE
	
	monster = closest_monster(quality) # using quality as range because lazy
	if monster is None:
		message('no enemy found.', libtcod.desaturated_yellow)
		return 'cancelled'
	#zap
	message('an arc of lightning leaps from the '+name+' and zaps '+
	monster.name+' for '+str(amount)+' hp!', libtcod.red)
	monster.fighter.take_damage(amount)
	message('the '+name+' falls apart!', libtcod.grey)

def confuse_effect(amount, name=None, quality=None, is_primary=False, effect_radius=1):
	#confuses an enemy for specified amounts of turns.
	if not quality: #quality is range
		quality = CONFUSE_RANGE
	monster = closest_monster(quality)
	if monster is None:	#no enemy found within max range
		message('no enemy in range.', libtcod.desaturated_yellow)
		return 'cancelled'
	#replace the monster ai with ConfusedMonster - after speficied turns it will change back
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai, num_turns=amount)
	monster.ai.owner = monster # tells new ai component who owns it
	message(monster.name+' gets blinded by the '+name+' and fumbles around.', libtcod.light_green)
	message('the '+name+' falls apart!',libtcod.grey)

##################
# INITIALIZATION #
##################

#create a player
player_fighter_component = Fighter(hp=30, defense=3, pow=4, death_function=player_death)
looker_component = Looker()
needs_component = Needs(hunger=99, thirst=99)
player = Object(0,0,'@',PLAYER_NAME, libtcod.white, blocks=True,
		fighter=player_fighter_component, look=looker_component,
		needs=needs_component)

#lists/arrays/whatevers, these are the containers for things
objects = [player]
game_msgs = []
inventory = []
#attack severity message arrays
attack_0_10_msg = ['glances off', 'fumbles and barely grazes', 'weakly punches', 'timidly attacks', 'jabs', 'trips into', 'loses momentum mid-swing'] # messages for damage of 0-10% of max HP
attack_10_35_msg = ['whacks', 'smacks', 'hits', 'gets a good hit on', 'punts', 'strikes', 'bashes', 'knocks', 'punches'] # messages for damage of 10-35% of max HP
attack_35_65_msg = ['gets a good hit on', 'lands a solid hit on'] # messages for damage of 35-65% of max HP
attack_65_85_msg = ['pummels','gives a good knockin\' to','does an uppercut on','stomps'] # messages for damage of 65-85% of max HP
attack_85_100_msg = ['does a german suplex on the', 'thoroughly pummels', 'dropkicks', 'lays the smackdown on'] # messages for damage of 85+% of max HP
#attack onomatopoeia.
attack_onoma_msg = ['biff', 'poff', 'boff', 'pow', 'bang', 'blam', 'pop', 'kapow', 'kablam', 'piff', 'pew', 'bop', 'slam', 'shabam', 'paf', 'taff', 'toff', 'ptaff', 'ptoff', 'kerblam', 
				'shazam', 'bam', 'slap', 'zonk', 'zlonk', 'bloop', 'oof', 'awk', 'bang-eth', 'clank', 'clonk', 'clash', 'clunk', 'crack', 'crunch', 'glip', 'glurp', 'blurp', 'kayow', 'kerplop',
				'klonk', 'klunk', 'kerklunk', 'ouch', 'plop', 'powie', 'rip', 'slosh', 'splat', 'sock', 'sploosh', 'thunk', 'bump', 'thwack', 'thwap', 'ugh', 'whack', 'wham', 'whamm', 'whammm', 
				'whap', 'zap', 'zlonk', 'zok', 'zowie', 'kerrrip']
#pickup message prefixes
pickup_prefix_msg = ['nice', 'sweet', 'cool', 'yes', 'alright', 'that\'s it', 'super', 'amok', 'hey', 'neat', 'sick', 'woo', 'whoa', 'right on', 'yeah', 'good', 'great', 'not bad', 'superb', 'excellent']
#sets font and root console properties
libtcod.console_set_custom_font('terminal12x12.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod WASTEOID '+VERSION, False, libtcod.RENDERER_SDL)
libtcod.sys_set_fps(LIMIT_FPS) #FPS limit
#creates an offscreen console and a log panel
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
log_panel = libtcod.console_new(SCREEN_WIDTH, LOG_PANEL_HEIGHT)
#makes map and fov map - called fov_init to avoid confusion with fov_map object
make_map()
fov_init()

#sets regen rate for all Fighters
regen_timer = HEALTH_REGEN_RATE
#sets timers for basic needs
hunger_timer = HUNGER_RATE
thirst_timer = THIRST_RATE

fov_recompute = True
game_state = 'playing'
player_action = None
fade=0
message(str(INTRO_MESSAGE), libtcod.desaturated_green)

##################
# MAIN GAME LOOP #
##################

while not libtcod.console_is_window_closed():
	#draws all objects in the objects list	
	render_all()
	
	if(fade < 255):
		libtcod.console_set_fade(fade,libtcod.black)
		libtcod.console_flush()
		fade+= 25
	
	libtcod.console_flush()
	#clear characters before moving to a new cell.
	clear_all()
	#handle keys
	player_action = handle_keys()
	#prints out name of object below player position
	walk_names = player.look.walk_names()
	
	if (game_state == 'playing' and (player_action !='no-move' and player_action!='enter-key')):
		print player_action
		for object in objects:
			if object.ai:
				object.ai.take_turn()
			if object.fighter:
				#health regen
				object.fighter.health_regen()
			if object.needs:
				object.needs.hunger_increase()
				object.needs.thirst_increase()
				
		if(walk_names and player_action == 'player-move'):
			message(walk_names)
		
	if (game_state == 'playing' or game_state == 'dead') and player_action == 'esc':
		break
		
	if (game_state == 'playing' or game_state == 'dead') and player_action == 'enter-key':
		#screenshot
		libtcod.sys_save_screenshot()
		message('//SCREENSHOT SAVED//')
