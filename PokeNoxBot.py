# -*- coding: utf-8 -*-

import json
import time
import io

import random
import sys
import os.path
import base64
import datetime
import PokemonIVCalculator
import math

import traceback

from PIL import Image, ImageOps, ImageDraw, ImageChops, ImageFilter

from math import ceil, radians, cos, sin, asin, sqrt
import re

assert sys.version_info >= (2,7)
assert sys.version_info < (3,0)

#When bag is full, item in this list will be dropped
ItemToDropList = ["Potion", "Super Potion", "Hyper Potion", "Revive", "Poke Ball", "Razz Berry"]
EvolveList = ["Pidgey", "Rattata", "Weedle", "Caterpie"]
KeepList = ["Magikarp"]
#Pokemon under this limit will be transfered
TransferCPLimit = 500
#If pokemon CP > GreatBallCPLimit the GreatBall will be used
GreatBallCPLimit = 600
UltraBallCPLimit = 700
RazzBerryCPLimit = 400
#WalkSpeed in meters per second, 7 is a safe/good value
Speed = 7
IVCalculator = PokemonIVCalculator.PokemonIVCalculator()
IVLimit = 0.9

#Rotate a python list
def rotate_list(l,n):
    return l[-n:] + l[:-n]

def geo_distance(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = sin(dlon/2)**2 + cos(lon1) * cos(lon2) * sin(dlat/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 
    return (c * r)*1000
    
def geo_walk_to(speed, lat1, lon1, alt1, lat2, lon2, alt2):
    new_lat = lat1
    new_lon = lon1
    new_alt = alt1
    
    travel_geo_points = []
    
    dist = geo_distance(lat1, lon1, lat2, lon2)
    steps = (float(dist))/(float(speed))
    if steps >= 1:
        dLat = (lat2 - lat1) / steps
        dLon = (lon2 - lon1) / steps
        dAlt = (alt2 - alt1) / steps
        for i in range(0, int(steps)):
            new_lat = lat1 + (dLat * (i+1))
            new_lon = lon1 + (dLon * (i+1))
            new_alt = alt1 + (dAlt * (i+1))
            #print "%f, %f, %f" % (new_lat, new_lon, new_alt)
            travel_geo_points.append([new_lat, new_lon, new_alt])
    #else:
        #print "%f, %f, %f" % (new_lat, new_lon, new_alt)
    #    travel_geo_points.append([new_lat, new_lon, new_alt])
    return travel_geo_points

def geo_point_from_kml(kml_filename, speed):
    geo_points = []
    f = open(kml_filename)
    for line in f:
        if re.match("[-+]?[0-9]*\.?[0-9]+,[-+]?[0-9]*\.?[0-9]+,[-+]?[0-9]*\.?[0-9]+", line):
            geo_point = line.strip().split(',')
            geo_points.append([float(geo_point[0]), float(geo_point[1]), float(geo_point[2])])
    f.close()

    loop_geo_points = []

    last_geo_point = None
    for cur_geo_point in geo_points:
        if not last_geo_point is None:
            loop_geo_points = loop_geo_points + geo_walk_to(speed, last_geo_point[0], last_geo_point[1], last_geo_point[2], cur_geo_point[0], cur_geo_point[1], cur_geo_point[2])
        last_geo_point = cur_geo_point
    loop_geo_points = loop_geo_points + geo_walk_to(speed, last_geo_point[0], last_geo_point[1], last_geo_point[2], geo_points[0][0], geo_points[0][1], geo_points[0][2])
    return loop_geo_points

def Tap(x, y):
    Command = "bin\\adb.exe shell input tap %d %d" % (x, y)
    os.system(Command)

def Swipe(x1, y1, x2, y2):
    Command = "bin\\adb.exe shell input swipe %d %d %d %d " % (x1, y1, x2, y2)
    os.system(Command)
    
def SwipeTime(x1, y1, x2, y2, t):
    Command = "bin\\adb.exe shell input swipe %d %d %d %d %d" % (x1, y1, x2, y2, t)
    os.system(Command)
    
def KeyEscap():
    Command = "bin\\adb.exe shell input keyevent 4"
    os.system(Command)

def TakePngScreenshot():
    while True:
        try:
            Command = "bin\\adb.exe shell \"screencap -p | busybox base64\""
            PngScreenshotData = os.popen(Command).read()
            PngScreenshotData = base64.b64decode(PngScreenshotData)
            break;
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            print "[!] Failed to get screen"
    return PngScreenshotData
 
def IsColorInCeil(ColorToCheck, RefColor, Ceil):
    if (RefColor[0]+(255*Ceil)) > ColorToCheck[0] > (RefColor[0]-(255*Ceil)):
        if (RefColor[1]+(255*Ceil)) > ColorToCheck[1] > (RefColor[1]-(255*Ceil)):
            if (RefColor[2]+(255*Ceil)) > ColorToCheck[2] > (RefColor[2]-(255*Ceil)):
                return True
    return False

def RemoveColor(img, Color, Ceil):
    pixdata = img.load()
    for y in xrange(img.size[1]):
        for x in xrange(img.size[0]):
            if IsColorInCeil(pixdata[x, y], Color, Ceil):
                pixdata[x, y] = (255, 255, 255)
               
def RemoveBlue(img, Limit):
    pixdata = img.load()
    for y in xrange(img.size[1]):
        for x in xrange(img.size[0]):
            if pixdata[x, y][2] > Limit:
                pixdata[x, y] = (255, 255, 255)
                        
def RemoveInSquare(img, x, y, xs, ys):
    pixdata = img.load()
    for yr in xrange(img.size[1]):
        for xr in xrange(img.size[0]):
            if (x+xs >= xr >= x) and (y+ys >= yr >= y):
                pixdata[xr, yr] = (255, 255, 255)
                
def RemoveNotInSquare(img, x, y, xs, ys):
    pixdata = img.load()
    for yr in xrange(img.size[1]):
        for xr in xrange(img.size[0]):
            if not((x+xs >= xr >= x) and (y+ys >= yr >= y)):
                pixdata[xr, yr] = (255, 255, 255)
                
def GetMeanColor(img, x, y, size=10):
    MeanColor = [0, 0, 0]
    pixdata = img.load()
    for xr in range(x-(size/2), x+(size/2)):
        for yr in range(y-(size/2), y+(size/2)):
            MeanColor[0] = MeanColor[0] + pixdata[xr, yr][0]
            MeanColor[1] = MeanColor[1] + pixdata[xr, yr][1]
            MeanColor[2] = MeanColor[2] + pixdata[xr, yr][2]
    MeanColor[0] = MeanColor[0]/(size**2)
    MeanColor[1] = MeanColor[1]/(size**2)
    MeanColor[2] = MeanColor[2]/(size**2)
    return MeanColor

ScreenShotCount = 0
def GetImgFromScreenShot():
    global ScreenShotCount
    ScreenShotCount += 1
    Screenshot = TakePngScreenshot()
    img = Image.open(io.BytesIO(Screenshot))
    img = img.convert("RGB")
    #img.save("tmp/%04d.png" % (ScreenShotCount))
    return img
    
def HighContrast(img, Limit=126):
    pixdata1 = img.load()
    for xr in xrange(img.size[0]):
        for yr in xrange(img.size[1]):
            if pixdata1[xr, yr] >= Limit:
                pixdata1[xr, yr] = 255
            else:
                pixdata1[xr, yr] = 0
            
#This is a best effort implementation !            
def GetPokemonFightNameCP():
    for i in range(10):
        PokemonName = None
        PokemonCP = None
        img1 = GetScreen()
        img1 = img1.crop(((35, 205, 35+387, 205+90)))
        img1 = ImageOps.grayscale(img1)
        ContrastPower = 216+random.randint(-10, 10)
        HighContrast(img1, ContrastPower)
        img1.save("tmp\\OUT_POKEFIGHT.png")
        PokemonNameCP =  ImgToString(img1, "bin\\POKENAMECP_CONFIG.txt").split(' ')
        print PokemonNameCP
        
        #New pokenom don't have the pokeball in front of name
        #['BLABLA', 'CP123'] 
        if len(PokemonNameCP) == 2:
            CPMark = PokemonNameCP[1][:2]
            CPMark = CPMark.replace('(', 'C')
            if CPMark == "CP":
                PokemonName = PokemonNameCP[0]
                PokemonCP = PokemonNameCP[1][2:]
        #@ is the pokeball
        #['@', 'BLABLA', 'CP123']
        elif len(PokemonNameCP) == 3:
            CPMark = PokemonNameCP[2][:2]
            CPMark = CPMark.replace('(', 'C')
            if CPMark == "CP":
                PokemonName = PokemonNameCP[1]
                PokemonCP = PokemonNameCP[2][2:]
            #TODO ['BLABLA', 'CP', '123']
        #['@', 'BLABLA', 'CP', '123']
        elif len(PokemonNameCP) == 4:
            CPMark = PokemonNameCP[2]
            CPMark = CPMark.replace('(', 'C')
            if PokemonNameCP[2] == "CP":
                PokemonName = PokemonNameCP[1]
                PokemonCP = PokemonNameCP[3]
        #print "-> %s %s" % (PokemonName, PokemonCP)
        if PokemonCP != None and PokemonName != None:
            #Little correction
            PokemonCP = PokemonCP.replace('O', '0')
            PokemonCP = PokemonCP.replace('L', '1')
            PokemonCP = PokemonCP.replace('l', '1')
            PokemonCP = PokemonCP.replace('Z', '2')
            PokemonCP = PokemonCP.replace('/', '7')
            PokemonCP = PokemonCP.replace('S', '5')
            PokemonCP = PokemonCP.replace('R', '8')
            if PokemonCP == "???":
                PokemonCP = "9999"
            try:
                PokemonCP = int(PokemonCP)
                #print ContrastPower
                return (FindRealPokemonName(PokemonName), PokemonCP)
            except:
                pass
        ClearScreen()
    return ("Unknown", 9999)

def GetImgFromFile(File):               
    img = Image.open(File)
    img = img.convert("RGB")
    return img
    
#TODO: class !!!
img = None
#TODO: We really need class !!
TotalExperience = 0

def AddExperience(ExperienceCount):
    global TotalExperience
    TotalExperience += ExperienceCount

def GetExperience():
    global TotalExperience
    return TotalExperience

def GetScreen():
    global img
    if img == None:
        img = GetImgFromScreenShot()
    return img
 
def ClearScreen():
    global img
    img = None
    
def IsOpenPokestop():
    img = GetScreen()
    #Outer
    MeanColor = GetMeanColor(img, 234, 780)
    #print MeanColor
    if MeanColor[0] < 150 and MeanColor[1] < 230 and MeanColor[2] > 240:
        return True
    #Inner border
    MeanColor = GetMeanColor(img, 180, 745)
    #print MeanColor
    if MeanColor[0] < 150 and MeanColor[1] < 230 and MeanColor[2] > 240:
        return True
    return False
 
def SpinPokestop():
    Swipe(432, 424, 109, 432)
    time.sleep(0.5)
    ClearScreen()
    
def IsSpinnedPokestop():
    img = GetScreen()
    #Outer
    MeanColor = GetMeanColor(img, 234, 780)
    if MeanColor[0] > 150 and MeanColor[1] < 150 and MeanColor[2] > 200:
        return True
    #Inner border
    MeanColor = GetMeanColor(img, 180, 745)
    #print MeanColor
    if MeanColor[0] > 150 and MeanColor[1] < 150 and MeanColor[2] > 200:
        return True
    return False
    
def ClosePokestop():
    #Tap(236, 736)
    KeyEscap()
    time.sleep(1)
    ClearScreen()

def CloseGym():
    #Tap(236, 736)
    KeyEscap()
    time.sleep(0.2)
    ClearScreen()
    
def FindPokestop():
    ReturnToMap()
    img = GetScreen().copy()
    #Apply a mask to keep only "Pokestop zone"
    PokeStopZone = (135, 420, 195, 180)
    mask = Image.new('L', (480, 800), 255)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((PokeStopZone[0],PokeStopZone[1],PokeStopZone[0]+PokeStopZone[2],PokeStopZone[1]+PokeStopZone[3]) , fill=0)
    img.paste((255, 255, 255), mask=mask)

    x, y, xs, ys = PokeStopZone
    #Remove Lured pokestop circle
    Frame = img.crop(((x, y, x+xs, y+ys)))
    RemoveColor(Frame, (179, 250, 255), 0.05)
    Frame.save("tmp\\OUT_POKESTOP.png")
    pixdata = Frame.load()
    SquareSize = 8
    for xr in range((SquareSize/2), xs-(SquareSize/2)):
        for yr in range((SquareSize/2), ys-(SquareSize/2)):
            #Only on blue like pixel
            if pixdata[xr, yr] != (255, 255, 255) and pixdata[xr, yr][2] > 230:
                MeanColor = GetMeanColor(Frame, xr, yr, SquareSize)
                if IsColorInCeil(MeanColor, [87, 255, 255], 0.05):
                    return [xr+(SquareSize/2)+x, yr+(SquareSize/2)+y]
                if IsColorInCeil(MeanColor, [64, 227, 252], 0.15):
                    return [xr+(SquareSize/2)+x, yr+(SquareSize/2)+y]
    return None
    
def BlackOrWhite(img):
    BlackCount = 0.0
    pixdata = img.load()
    for xr in xrange(img.size[0]):
        for yr in xrange(img.size[1]):
            if pixdata[xr, yr] != (255, 255, 255):
               pixdata[xr, yr] = (0, 0, 0)
               BlackCount += 1
    return (BlackCount/(img.size[0]*img.size[1]))*100
    
def IsDay():
    Hour = datetime.datetime.now().hour  
    if Hour >= 7 and Hour <= 19:
        return True
    return False

def RemoveColorList(img, ColorList):
    pixdata = img.load()
    for x in xrange(img.size[0]):
        for y in xrange(img.size[1]):
            if pixdata[x, y] in ColorList:
                pixdata[x, y] = (255, 255, 255)
                
def FindPokemonPosition(img, SquareSize=4):
    pixdata = img.load()
    for xr in range(SquareSize/2, img.size[0]-(SquareSize/2)):
        for yr in range(SquareSize/2, img.size[1]-(SquareSize/2)):
            if pixdata[xr, yr] == (0, 0, 0):
                FalsePositiv = GetMeanColor(img, xr, yr, SquareSize)
                Score = (FalsePositiv[0]+FalsePositiv[1]+FalsePositiv[2])/3
                if Score < 70:
                    return [xr, yr]
    return None
    
def FindPokemon():
    ReturnToMap();
    #TestFindPokemon()
    img = GetScreen().copy()
    #Remove the player
    RemoveInSquare(img, 227, 482, 22, 40)
    #Remove the Experience notification
    RemoveInSquare(img, 24, 600, 115, 70)
    
    #Apply amask to keep only "Pokemon zone"
    mask = Image.new('L', (480, 800), 255)
    draw = ImageDraw.Draw(mask)
    PokemonZone = (65, 420, 135+300, 438+250)
    draw.ellipse(PokemonZone, fill=0)
    img.paste((255, 255, 255), mask=mask)
    
    Frame = img.crop((PokemonZone))
    Frame = ImageOps.posterize(Frame, 2)
    
    ColorBlackList = []
    if IsDay() == True:
        #Day Road
        ColorBlackList.append((64, 128, 128))
        ColorBlackList.append((0, 128, 128))
        #Green
        ColorBlackList.append((0, 192, 128))
        ColorBlackList.append((128, 192, 128))
        ColorBlackList.append((128, 192, 64))
        ColorBlackList.append((64, 192, 128))
        ColorBlackList.append((64, 192, 64))
        #Day Road Boarder
        ColorBlackList.append((192, 192, 128))
    else:
        #Road
        ColorBlackList.append((64, 128, 192))
        #Green
        ColorBlackList.append((64, 128, 128))
        ColorBlackList.append((0, 128, 128))
        ColorBlackList.append((0, 64, 128))
        ColorBlackList.append((0, 64, 64))
        ColorBlackList.append((64, 128, 64))
        #Night Road Boarder
        ColorBlackList.append((128, 128, 128))
        
    #Spinned Pokestop 
    ColorBlackList.append((192, 128, 192))
    ColorBlackList.append((64, 64, 192))
    ColorBlackList.append((128, 64, 192))
    #Lured Pokestop 
    ColorBlackList.append((192, 64, 192))
    #Pokestop 
    ColorBlackList.append((0, 128, 192))
    ColorBlackList.append((64, 192, 192))
    ColorBlackList.append((0, 192, 192))
    ColorBlackList.append((0, 64, 192))
    #Lured Pokestop Circle
    ColorBlackList.append((128, 192, 192))
    #Lured Pokestop Flowers
    ColorBlackList.append((192, 192, 192))
    #Green rustles
    ColorBlackList.append((0, 128, 64))
    ColorBlackList.append((128, 128, 64))
    ColorBlackList.append((128, 192, 128))
    ColorBlackList.append((0, 192, 0))
    ColorBlackList.append((128, 192, 0))
    ColorBlackList.append((0, 64, 0))
    ColorBlackList.append((64, 192, 0))
    ColorBlackList.append((64, 192, 128))
    ColorBlackList.append((0, 128, 0))
    
    RemoveColorList(Frame, ColorBlackList)
    
    Frame.save("tmp\\OUT_COLOR.png")
    BlackRatio = BlackOrWhite(Frame)
    Frame.save("tmp\\OUT_BW.png")
    #Frame = Image.open("TEST_POKE.png")
    #Search for big Pokemon before small one
    for i in range(10, 2, -2):
        PokemonPosition = FindPokemonPosition(Frame, i)
        if not PokemonPosition is None:
            PokemonPosition[0] += PokemonZone[0]
            PokemonPosition[1] += PokemonZone[1]
            return PokemonPosition

    return None

def ThrowPokeball(Power):
    #Far 100
    #Near 400
    SwipeTime(236, 780, 236, 30+Power, 200)
    #Fast Pokeball return
    #SwipeTime(73, 600, 245, 734, 500)
    ClearScreen()

def IsPokemonFightOpen():
    img = GetScreen()
    pixdata = img.load()
    return IsColorInCeil(pixdata[426, 67], (241, 249, 241), 0.01)
 
def IsGymOpen():
    img = GetScreen()
    pixdata = img.load()
    #White part of the "plateau"
    if IsColorInCeil(pixdata[403, 560], (255, 255, 255), 0.01) == False:
        return False
    #Close cross
    if IsColorInCeil(pixdata[240, 740], (34, 136, 153), 0.01) == False:
        return False
    return True
    
    
def IsOnMap():
    img = GetScreen()
    pixdata = img.load()
    return IsColorInCeil(pixdata[237, 703], (255, 57, 69), 0.01)
    
def IsCatchSucess():
    img = GetScreen()
    #img = GetImgFromFile("CatchSuccess.png")
    pixdata = img.load()
    if IsColorInCeil(pixdata[44, 227], (254, 255, 254), 0.005) and IsColorInCeil(pixdata[22, 518], (247, 255, 245), 0.01):
        return True
    return False

    
def PokemonWorker(PokemonPosition):
    print "[!] Going to fight with %d %d !" % (PokemonPosition[0], PokemonPosition[1])
    Tap(PokemonPosition[0], PokemonPosition[1])
    ClearScreen()
    time.sleep(0.3)
    bIsPokemonFightOpened = False
    #Check if the click successed
    if IsOnMap() == True:
        print "[!] Click failed !"
        return None
    
    #Wait for fight
    for i in range(0, 5):
        #time.sleep(1)
        if IsPokemonFightOpen() == True:
            bIsPokemonFightOpened = True
            break;
        if IsGymOpen() == True:
            print "[!] Holy... This is a Gym"
            CloseGym()
            break
        #We maybe clicked on a PokeStop...
        if IsOpenPokestop() == True:
            print "[!] Holy... This is a Pokestop"
            PokestopWorker([0,0])
            break
        if IsSpinnedPokestop() == True:
            print "[!] Holy... This is a Spinned Pokestop"
            ClosePokestop()
            break
        if IsPokeBoxFull() == True:
            print "[!] The PokeBox is full !"
            #Close the pop-up
            #Tap(345, 419)
            KeyEscap()
            time.sleep(0.5)
            ClearScreen()
            TransferLowCPPokemons(10)
            #Return true to refight the pokemon
            return True
        print "[!] Wait for Pokemon fight..."
        time.sleep(0.5)
        ClearScreen()
    
    if bIsPokemonFightOpened == False:  
        #This is a big fail maybe a gym detected as Pokemon
        return None
    
    #Get the Name and the CP of this Pokemon
    (PokemonName, PokemonCP) = GetPokemonFightNameCP()
    print "[!] Seems to be a %s at %d" % (PokemonName, PokemonCP)
    
    #Select the right Poke Ball
    SelectedPokeball = "Poke Ball"
    if PokemonCP >= UltraBallCPLimit:
        print "[!] Using a Ultra Ball %d > %d" % (PokemonCP, UltraBallCPLimit)
        if UseUltraBall() == False:
            if UseGreatBall() == True:
                SelectedPokeball = "Great Ball" 
        else:
           SelectedPokeball = "Ultra Ball" 
    elif PokemonCP >= GreatBallCPLimit:
        print "[!] Using a Great Ball %d > %d" % (PokemonCP, GreatBallCPLimit)
        if UseGreatBall() == True:
            SelectedPokeball = "Great Ball" 

    #Use a Razz Berry if one
    if PokemonCP >= RazzBerryCPLimit:
        if UseRazzBerry() == True:
            print "[!] Using Razz Berry"

    bIsPokemonHitted = False
    ThrowCount = 0
    while True:
        if bIsPokemonHitted == False:
            LastPower = random.randint(0,500)
        else:
            print "[!] Using last "+SelectedPokeball+" power"
        if ThrowCount > 30 :
            print "[!] Pokemon too hard, exiting the fight !"
            ClosePokemonFight()
            #Return false to avoid refight this pokemon
            return False
        #TODO Detect pokemon distance
        print "[!] Throwing a "+SelectedPokeball+" (%d)" % LastPower
        ThrowPokeball(LastPower)
        ThrowCount += 1
        time.sleep(1)
        bIsPokemonFightOpened = False
        bIsCatchSuccess = False
        bIsOnMap = False
        StressCount = 0
        for i in range(30):
            if IsPokemonFightOpen() == True:
                bIsPokemonFightOpened = True
                break
            if IsCatchSucess() == True:
                bIsCatchSuccess = True
                break
            if IsOnMap() == True:
                bIsOnMap = True
                break
            if IsGameCrashed() == True:
                return None
            print "[!] #STRESS..."
            StressCount += 1
            ClearScreen()
            
        if bIsCatchSuccess == True:
            print "[!] Pokemon caught !"
            break
            
        if bIsOnMap == True:
            print "[!] Pokemon flee !"
            return False
        
        if StressCount == 0:
            print "[!] No more pokeball !"
            ClosePokemonFight()
            return None
            
        if StressCount >= 4:
            bIsPokemonHitted = True
        else:
            bIsPokemonHitted = False

    #Let the popup to fully open
    time.sleep(0.5)
    #Close "sucess" Pop-up
    Tap(239, 526)
    time.sleep(0.5)
    ClearScreen()
    while IsPokemonOpen() == False:
        #Tap anywhere will close the sucess pop-up
        Tap(50,50)
        time.sleep(0.5)
        ClearScreen()
    print "[!] On Pokemon"
        
    #We are here on the pokemon statistics
    PokemonName = GetPokemonName()
    PokemonCP = GetPokemonCP()
    print "[!] This is a %s CP:%d" % (PokemonName, PokemonCP)
    PokemonIV = GetPokemonIV(PokemonName, PokemonCP)
    print PokemonIV
    if (not PokemonIV is None) and PokemonIV['perfection'] >= IVLimit:
        ClosePokemon()
    elif PokemonName in EvolveList:
        EvolvePokemon()
        TransferPokemon()
    elif PokemonCP < TransferCPLimit and (not PokemonName in KeepList):
        TransferPokemon()
    else:
        ClosePokemon()
        
    AddExperience(100)
    
    print "[!] Waiting return to map..."
    ReturnToMap()
    return True

def ClosePokemon():
    #Tap(239, 740)
    KeyEscap()
    time.sleep(0.3)
    ClearScreen()
    
def PokestopWorker(PokeStopPosition):
    print "[!] Working on Pokestop %d %d" % (PokeStopPosition[0], PokeStopPosition[1])
    Tap(PokeStopPosition[0], PokeStopPosition[1])
    time.sleep(0.6)
    ClearScreen()
    if IsOnMap() == True:
        print "[!] Click failed !"
        return False
    bOpenPokestopSuccess = False
    for i in range(5):
        if IsPokestopTooFar() == True:
            print "[!] Pokestop is too far !"
            ClosePokestop()
            break
        if IsOpenPokestop() == True:
            bOpenPokestopSuccess = True
            break
        if IsSpinnedPokestop() == True:
            print "[!] Pokestop already spinned... Something wrong..."
            ClosePokestop()
            break
        if IsPokemonFightOpen():
            print "[!] Holy... This is a pokemon !"
            PokemonWorker([0,0])
            break
        if IsGymOpen():
            print "[!] Holy... This is a Gym"
            CloseGym()
        print "[!] Wait for open pokestop"
        ClearScreen()
            
    if bOpenPokestopSuccess == True:
        SpinPokestop()
        bIsSpinnedPokestop = False
        for i in range(3):
            if IsSpinnedPokestop() == True:
                bIsSpinnedPokestop = True
                break
            print "[!] Wait for spinned pokestop"
            ClearScreen()
        
        bIsBagFull = IsBagFull()
        
        ClosePokestop()
        while IsOnMap() == False:
            print "[!] Waiting return to the map"
            ClearScreen()

        if bIsBagFull == True:
            print "[!] The bag is full..."
            CleanInventory()
         
        if bIsSpinnedPokestop == True:
            AddExperience(50)

        bOpenPokestopSuccess = bIsSpinnedPokestop
    return bOpenPokestopSuccess

def random_lat_long_delta():
    return ((random.random() * 0.00001) - 0.000005) * 3
    
def SetPosition(Position):
    Position[1] += random_lat_long_delta()
    Position[0] += random_lat_long_delta()
    Command = "bin\\adb.exe shell \"setprop persist.nox.gps.longitude %f && setprop persist.nox.gps.latitude %f && setprop persist.nox.gps.altitude %f\"" % (Position[0], Position[1], Position[2])
    #Saved position
    f = open("tmp/saved_position.txt", "w")
    f.write("%f,%f,%f" % (Position[1], Position[0], Position[2]))
    f.close()
    os.system(Command)
    ClearScreen()
    
def TransferPokemon():
    if IsPokemonOpen() == False:
        return False
    #Options
    Tap(418, 741)
    time.sleep(0.1)
    #Tap Transfert
    Tap(423, 651)
    time.sleep(0.1)
    #Validation
    #Tap(236,452) #0.31
    Tap(240, 500) #0.33
    time.sleep(1)
    
def OpenPokemonMenu():
    if IsOnMap() == False:
        print "[!] Not on the map !"
        return False
    #Open Menu
    Tap(236, 736)
    time.sleep(0.1)
    #Open Pokemon Menu
    Tap(104, 659)
    time.sleep(0.2)
    return True

def CloseMenu():
    KeyEscap()
    time.sleep(0.3)
    ClearScreen()
    
def TransferLowCPPokemons(Number):
    print "[!] Low CP pokemon will be transfered..."
    if OpenPokemonMenu() == False:
        print "[!] Failed to OpenPokemonMenu"
        return False
    #Tap CP
    Tap(415, 742) 
    time.sleep(0.1)
    #Select CP
    #Tap(414, 631)#0.310
    Tap(415, 650) #0.33.0
    time.sleep(0.1)
    #ScrollDown
    SwipeTime(461, 123, 461, 12000, 300)
    
    for i in range(0, Number):
        print "[!] Transfering a low CP pokemon (%d/%d)" % (i+1, Number)
        #Tap Down Left pokemon
        Tap(83,619)
        time.sleep(0.5)
        ClearScreen()
        if GetPokemonName() in EvolveList:
            EvolvePokemon()
        #    ClosePokemon()
        #else:
        TransferPokemon()
    
    #Close Menu
    #Tap(236, 736)
    CloseMenu()
    #Wait to be on the map
    time.sleep(1)
    
def IsGameCrashed():
    img = GetScreen()
    pixdata = img.load()
    if IsColorInCeil(pixdata[112, 451], (0, 0, 0), 0.01) and IsColorInCeil(pixdata[372, 449], (0, 0, 0), 0.01):
        return True
    if IsColorInCeil(pixdata[112, 451], (40, 40, 40), 0.01) and IsColorInCeil(pixdata[372, 449], (40, 40, 40), 0.01):
        return True
    MeanColor = GetMeanColor(img, 334, 291, 10)
    if IsColorInCeil(MeanColor, [159, 156, 155], 0.01):
        return True
    return False
    
def IsPokeBoxFull():
    img = GetScreen()
    pixdata = img.load()
    return IsColorInCeil(pixdata[345, 419], (54, 206, 167), 0.005)

#TODO: This shit is language dependent !
def IsPokestopTooFar():
    img = GetScreen()
    pixdata = img.load()
    return IsColorInCeil(pixdata[379,653], (229, 127, 179), 0.005)

def IsBagFull():
    img = GetScreen()
    pixdata = img.load()
    return IsColorInCeil(pixdata[310, 398], (228, 127, 177), 0.005)

def ClosePokemonFight():
    Tap(53, 65)
    ClearScreen()

#Todo: Take a while...
def ZoomOut():
    Command = "bin\\adb.exe push bin\\Zoomout.txt /sdcard/Zoomout.txt"
    os.system(Command)
    Command = "bin\\adb.exe shell sh /sdcard/Zoomout.txt"
    os.system(Command)
    
def RestartApplication():
    #Close the game
    Command = "bin\\adb shell am force-stop com.nianticlabs.pokemongo"
    os.system(Command)
    #Start the game
    Command = "bin\\adb shell monkey -p com.nianticlabs.pokemongo -c android.intent.category.LAUNCHER 1"
    os.system(Command)
    #Close the error popup
    #Tap(240, 444)
    #time.sleep(0.5)
    #Start the game
    #Tap(334, 291)
    while IsOnMap() == False:
        Tap(235, 457)
        ClearScreen()
        print "[!] Waiting for map..."
        time.sleep(1)
    #Sometime got a "flash" map
    time.sleep(2)
    ClearScreen()
    while IsOnMap() == False:
        Tap(235, 457)
        ClearScreen()
        print "[!] Waiting for map..."
        time.sleep(1)
    ZoomOut()
    ClearScreen()

#TODO: Handle multiple egg incubators
def AddEggInIncubator():
    if OpenPokemonMenu() == False:
        print "[!] Failed to OpenPokemonMenu"
        return False
    time.sleep(0.5)
    #Tap on EGGS
    Tap(357, 85)
    time.sleep(0.2)
    #Tap on Upper left Egg
    Tap(80, 217)
    time.sleep(0.2)
    #Tap on START INCUBATION
    Tap(231, 507)
    time.sleep(0.2)
    #Tap on first incubator (always a free when a free incubator is available)
    Tap(67, 619)
    time.sleep(0.2)
    #Close Egg Screen
    #ClosePokestop()
    KeyEscap()
    #Close Eggs Screen
    #ClosePokestop()
    ClosePokemonMemu()
    KeyEscap()
    return True
    
#TODO !
def ReturnToMap():
    for i in range(4):
        if IsOnMap() == True:
            return True
        #Sometime got a crash of pokemongo
        if IsGameCrashed():
            RestartApplication()
            return True
        #This is shit !
        if IsPokemonFightOpen():
            PokemonWorker([0,0])
            #No need to close
            return True
        if IsEggHatched() == True:
            print "[!] EGG HATCHED !!!!!!!!!!"
            #Tap anywhere on screen
            Tap(200, 440)
            ClearScreen()
            print "[!] Waiting end of animation"
            while IsPokemonOpen() == False:
                ClearScreen()
            AddExperience(500)
            ClosePokemon()
            time.sleep(2)
            ClearScreen()
            #Be sur in case we have multiple egg at the same time
            if IsOnMap() == True:
                AddEggInIncubator()
            return True
        if IsPokestopTooFar():
            ClosePokestop()
            return True
        if IsSpinnedPokestop():
            ClosePokestop()
            return True
        if IsOpenPokestop():
            PokestopWorker([0,0])
            #No need to close, this is close by PokestopWorker
            return True
        if IsGymOpen():
            CloseGym()
            return True
        if IsPokeBoxFull():
            #Close the pop-up
            Tap(345, 419)
            ClearScreen()
            time.sleep(0.5)
            TransferLowCPPokemons(50)
            return True
        time.sleep(0.5)
        #Last Hope... medals,...
        if i == 2:
            print "[!] LAST HOPE TO ESCAPE !"
            for j in range(4):
                KeyEscap()
            Tap(0, 0)
            ClosePokestop()
            #Close speed alert
            Tap(236, 536)
            time.sleep(1)
        ClearScreen()
    print "[!] Don't know where we are.... Exiting"
    img = GetScreen()
    img.save("OUT_FAIL.png")
    RestartApplication()
    return False
   
def ImgToString(img, ConfigFile=None):
    img.save("tmp\\ocr.png")
    Command = "bin\\tesseract.exe --tessdata-dir bin\\tessdata tmp\\ocr.png tmp\\ocr "
    if ConfigFile != None:
        Command += ""+ConfigFile+" "
    Command += "> nul 2>&1"
    #print Command
    os.system(Command)
    f = open("tmp\\ocr.txt")
    StringContent = f.readline().strip()
    f.close()
    return StringContent

def GetPokemonName():
    img = GetScreen()
    PokeNameZone = (24, 353, 24+430, 353+52)
    Frame = img.crop(((PokeNameZone)))
    PokemonName = ImgToString(Frame, "bin\\POKENAME_CONFIG.txt")
    return FindRealPokemonName(PokemonName)
    
def IsEvolvable():
    img = GetScreen()
    pixdata = img.load()
    return IsColorInCeil(pixdata[218, 703], (36, 204, 170), 0.005)
 
def IsPokemonOpen():
    img = GetScreen()
    pixdata = img.load()
    return (pixdata[33, 331] == (250, 250, 250) and pixdata[448, 675] == (250, 250, 250))
    
def EvolvePokemon():
    if IsPokemonOpen() == False:
        print "[!] Not on a Pokemon !"
        return False
    if IsEvolvable() == False:
        print "[!] This Pokemon is not evolvable !"
        return False
    #Evolve !
    Tap(144, 707)
    time.sleep(0.2)
    #Validation
    Tap(239, 420)
    ClearScreen()
    print "[!] Waiting end of evolution..."
    time.sleep(10)
    while IsPokemonOpen() == False:
        ClearScreen()
        time.sleep(1)
    AddExperience(500)
    print "[!] Evolution done !"
    return True
    
def IsEggHatched():
    img = GetScreen()
    pixdata = img.load()
    #print pixdata[18, 780]
    return IsColorInCeil(pixdata[18, 780], (204, 245, 237), 0.005)
    

def CleanInventory():
    print "[!] Clean inventory..."
    if IsOnMap() == False:
        print "[!] Not on the map !"
        return False
    Tap(236, 736)
    time.sleep(1)
    Tap(372, 651)
    time.sleep(1)
    ClearScreen()
    while True:
        bIsDroppedItem = False
        img = GetScreen()
        for i in range(3, -1, -1):
            ItemNameZone = (152, 140+(170*i), 152+272, 140+(170*i)+39)
            Frame = img.crop(((ItemNameZone)))
            #TODO: use user-patterns
            ItemName = ImgToString(Frame).replace("\xc3\xa9","e")
            if ItemName == "":
                #Close Inventory
                Tap(236, 736)
                ClearScreen()
                return False
            if ItemName in ItemToDropList:
                print "[!] Dropping %s " % (ItemName)
                #Tap on trash
                Tap(440, 140+(170*i))
                time.sleep(1)
                #1sec for 20 elements
                SwipeTime(351, 355, 351, 355, 2000)
                #Tap OK
                Tap(236, 511)
                time.sleep(0.5)
                bIsDroppedItem = True
        if bIsDroppedItem == False:
            SwipeTime(399, 790, 399, 799-(116*4), 1000)
            time.sleep(2)
        ClearScreen()
    #Close Inventory
    KeyEscap()
    ClearScreen()
    return False
 
def CloseBackPack():
    KeyEscap()
    ClearScreen()
    
def UseItem(ItemToUseName):
    img = GetScreen()
    for i in range(3, -1, -1):
        ItemNameZone = (152, 140+(170*i), 152+272, 140+(170*i)+39)
        Frame = img.crop(((ItemNameZone)))
        #TODO: use user-patterns
        ItemName = ImgToString(Frame).replace("\xc3\xa9","e")
        if ItemName == "":
            break
        if ItemName in ItemToUseName:
            Tap(152, 140+(170*i))
            return True
    #Same position as Pokestop
    CloseBackPack()
    return False

def GetPokemonCP():
    #Need to that because of some Pokemon animation
    for i in range(5):
        img = GetScreen()
        Frame = img.crop(((160, 49, 160+121, 49+38)))
        RemoveColor(Frame, (255, 255, 255), 0.2)
        BlackOrWhite(Frame)
        PokemonCP = ImgToString(Frame, "bin\\CP_CONFIG.txt").upper()
        #print PokemonCP
        if PokemonCP[:2] == "CP":
            try:  
                return int(PokemonCP[2:])
            except:
                pass
        ClearScreen()
    return 9999
        
def OpenBackPack():
    #Tap on Back Pack
    Tap(418, 737)
    time.sleep(0.5)
    ClearScreen()
    
def UseRazzBerry():
    if IsPokemonFightOpen() == False:
        print "[!] Impossible to use Razz Berry here !"
        return False
    OpenBackPack()
    if UseItem("Razz Berry") == True:
        #Tap on Razz Berry to really use it
        Tap(237, 600)
        #Animation of Razz Berry
        time.sleep(1.5)
        ClearScreen()
        return True
    return False
    
def UseGreatBall():
    if IsPokemonFightOpen() == False:
        print "[!] Impossible to use Great Ball here !"
        return False
    OpenBackPack()
    if UseItem("Great Ball") == True:
        #Animation of Great Ball
        time.sleep(0.2)
        ClearScreen()
        return True
    return False

def UseUltraBall():
    if IsPokemonFightOpen() == False:
        print "[!] Impossible to use Ultra Ball here !"
        return False
    OpenBackPack()
    if UseItem("Ultra Ball") == True:
        #Animation of Great Ball
        time.sleep(0.2)
        ClearScreen()
        return True
    return False

def ClosePokemonMemu():
    KeyEscap()
    ClearScreen()
    
#TODO: Optimize this!
def EvolveAllPokemon():
    OpenPokemonMenu()
    #Tap on Upper Left Pokemon
    Tap(77, 239)
    time.sleep(0.5)
    ClearScreen()
    for i in range(250):
        #print GetPokemonCP()
        if IsEvolvable() == True and GetPokemonName() in EvolveList:
            print "Evolvable"
            EvolvePokemon()
            ClosePokemon()
            #Tap on Upper Left Pokemon
            Tap(77, 239)
            time.sleep(0.5)
            #This is not optimized at all !
            for j in range(i):
                #Go to Next Pokemon
                Tap(460, 200)
            ClearScreen()
        #Go to Next Pokemon
        Tap(460, 200)
        time.sleep(1)
        ClearScreen()
    ClosePokemon()
    ClosePokemonMenu()
    
def GetPokemonLevel():
    arcCenter = 240
    arcInitialY = 285
    radius = 183
    img = GetScreen()
    pixdata = img.load()
    trainerLevel = GetTrainerLevel()*2
    estimatedPokemonLevel = trainerLevel + 3;

    for estPokemonLevel in range(estimatedPokemonLevel, 2, -1):
        angleInDegrees = (IVCalculator.levels[int(estPokemonLevel - 1)]['cpScalar'] - 0.094) * 202.037116 / IVCalculator.levels[trainerLevel - 1]['cpScalar']
        if (angleInDegrees > 1.0 and trainerLevel < 60) :
            angleInDegrees -= 0.5
        elif (trainerLevel >= 60):
            angleInDegrees += 0.5
        angleInRadians = (angleInDegrees + 180) * math.pi / 180.0;
        x = int(arcCenter + (radius * math.cos(angleInRadians)));
        y = int(arcInitialY + (radius * math.sin(angleInRadians)));
        if pixdata[x, y] == (255, 255, 255):
            return estPokemonLevel
    return 0

#TODO: A CLASS IS REALLY NEEDED !
TrainerLevel = -1
def UpdateTrainerLevel():
    global TrainerLevel
    img = GetScreen()
    TrainerLevelZone = (70, 734, 70+40, 734+23)
    img = img.crop((TrainerLevelZone))
    img = ImageOps.grayscale(img)
    HighContrast(img, 220)
    img = ImageChops.invert(img)
    NewTrainerLevel = ImgToString(img, "bin\\LEVEL_CONFIG.txt")
    try:
        NewTrainerLevel = int(NewTrainerLevel)
        if NewTrainerLevel >= 1 and NewTrainerLevel <= 40 and NewTrainerLevel >= TrainerLevel:
            TrainerLevel = NewTrainerLevel
            return True
    except:
        pass
    return False
 
def GetTrainerLevel():
    global TrainerLevel
    return TrainerLevel
    
def GetPokemonHP():
    img = GetScreen()
    PokeHPZone = (129, 418, 223+129, 31+418)
    img = img.crop((PokeHPZone))
    PokemonHP = ImgToString(img, "bin\\HP_CONFIG.txt")
    PokemonHP = int(PokemonHP.split('/')[1])
    return PokemonHP
    
def GetPokemonStarDust():
    img = GetScreen()
    PokeHPZone = (262, 635, 262+66, 635+21)
    img = img.crop((PokeHPZone))
    PokemonStartDust = ImgToString(img, "bin\\STARDUST_CONFIG.txt")
    PokemonStartDust = int(PokemonStartDust)
    return PokemonStartDust    
  
def GetPokemonIV(PokemonName=None, PokemonCP=None):
    PokemonLevel = GetPokemonLevel()
    if PokemonName == None:
        PokemonName = GetPokemonName()
    if PokemonCP == None:
        PokemonCP = GetPokemonCP()
    PokemonHP = GetPokemonHP()
    PokemonStarDust = GetPokemonStarDust()
    return IVCalculator.EvaluatePokemon(PokemonName, PokemonCP, PokemonHP, PokemonStarDust, True, PokemonLevel)

def levenshtein_distance(first, second):
    """Find the Levenshtein distance between two strings."""
    if len(first) > len(second):
        first, second = second, first
    if len(second) == 0:
        return len(first)
    first_length = len(first) + 1
    second_length = len(second) + 1
    distance_matrix = [[0] * second_length for x in range(first_length)]
    for i in range(first_length):
       distance_matrix[i][0] = i
    for j in range(second_length):
       distance_matrix[0][j]=j
    for i in xrange(1, first_length):
        for j in range(1, second_length):
            deletion = distance_matrix[i-1][j] + 1
            insertion = distance_matrix[i][j-1] + 1
            substitution = distance_matrix[i-1][j-1]
            if first[i-1] != second[j-1]:
                substitution += 1
            distance_matrix[i][j] = min(insertion, deletion, substitution)
    return distance_matrix[first_length-1][second_length-1]
    
def FindRealPokemonName(PokemonName):
    MinScore = 9999
    RealPokemonName = None
    for pokemon in IVCalculator.PokemonInfoList:
        CurrentScore = levenshtein_distance(PokemonName, pokemon['name'])
        if CurrentScore < MinScore:
            MinScore = CurrentScore
            RealPokemonName = pokemon['name']
    return RealPokemonName
     
#Core...

#AddEggInIncubator()
#Tap(272, 800)
#Swipe(539, 200, 0, 200)
#Tap(490, 128)
#img = GetImgFromFile("output.png")
#PokemonPosition = FindPokemon()
#PokeStopPosition = FindPokestop(img)
#img = GetImgFromScreenShot()
#FindPokemon()
#print GetMeanColor(img, 251, 478 )
#print FindPokemon()
#img.save("OUT.png")
#print PokemonPosition
#print IsCatchSucess()
#CatchPokemon([376, 512])
#CleanInventory()
#print IsCatchSucess()
#TransfertPokemon(30)
#img = Image.open("output.png")
#print IsBagFull()
#print IsGymOpen()
#print IsOpenPokestop()
#print IsPokemonOpen()
#print GetPokemonName()
#print IsEvolvable()
#print EvolvePokemon()
#TransferLowCPPokemons(50)
#print GetPokemonCP()
#EvolveAllPokemon()
#print GetPokemonFightNameCP()
#PokemonLevel = GetPokemonLevel()
#PokemonName = GetPokemonName()
#PokemonCP = GetPokemonCP()
#PokemonHP = GetPokemonHP()
#PokemonStarDust = GetPokemonStarDust()
#while True:
#    UpdateTrainerLevel()
#    print GetTrainerLevel()
#    ClearScreen()
#print IVCalculator.EvaluatePokemon(PokemonName, PokemonCP, PokemonHP, PokemonStarDust, True, PokemonLevel)
# OpenPokemonMenu()
# #Tap on Upper Left Pokemon
# Tap(77, 239)
# time.sleep(0.5)
# ClearScreen()
# while True:
    # PokemonIV = GetPokemonIV()
    # if PokemonIV == None:
        # break
    # print PokemonIV
    # #Go to Next Pokemon
    # Tap(460, 200)
    # time.sleep(1)
    # ClearScreen()
#print FindRealPokemonName("Ridgc@çcotta")
#sys.exit(0)



loop_geo_points = geo_point_from_kml("Levalois.kml", Speed)

#Searching for the nearest point 
if os.path.isfile("tmp/saved_position.txt"):
    f = open("tmp/saved_position.txt", 'r')
    line = f.read().strip()
    if re.match(".*,.*,.*", line):
        saved_position = line.split(',')
        saved_position[0] = float(saved_position[0])
        saved_position[1] = float(saved_position[1])
        saved_position[2] = float(saved_position[2])
        min_distance = 99999999
        min_distance_index = 0
        current_index = 0
        for geo_point in loop_geo_points:
            distance_to_saved_point = geo_distance(saved_position[0], saved_position[1], geo_point[1], geo_point[0])
            if distance_to_saved_point < min_distance:
                min_distance_index = current_index
                min_distance = distance_to_saved_point
            current_index += 1
        loop_geo_points = rotate_list(loop_geo_points, (-1 * min_distance_index))
		#Teleport Security

Count = 0
#Set Initial position
SetPosition(loop_geo_points[0])
StartTime = time.time()
while True:
    for geo_point in loop_geo_points:
        if Count%(50/Speed)==0:
            ReturnToMap()
            UpdateTrainerLevel()
            SetPosition(geo_point)
            #Waiting for end of running...
            time.sleep(4.5)
            ClearScreen()
            print "[!] Looking around..."
            
            #Pokestop first to grab some pokeball
            while True:
                print "[!] Looking for Pokestop"
                PokeStopPosition = FindPokestop()
                if PokeStopPosition is None:
                    print "[!] No more Pokestop found."
                    break
                if PokestopWorker(PokeStopPosition) == False:
                    print "[!] Something failed..."
                    break
            
            while True:
                print "[!] Looking for pokemon"
                #Clearing the screen because PokestopWorker can be long...
                ClearScreen()
                PokemonPosition = FindPokemon()
                if PokemonPosition == False:
                    print "[!] This place is near a Gym !"
                    break
                if PokemonPosition is None:
                    print "[!] No more Pokemon not found."
                    break
                PokemonWorkerReturn = PokemonWorker(PokemonPosition)
                if PokemonWorkerReturn == None:
                    print "[!] This place is near a Gym ?"
                    break
                if PokemonWorkerReturn == False:
                    if IsGymOpen() == True:
                        CloseGym()
                        print "[!] This place is near a Gym !"
                        break
            #Print estimated exprience for kikoo-time !
            print "[!] ~%d Exp/h" % ((GetExperience()/(time.time()-StartTime))*60*60)
        Count += 1
        #SetPosition(geo_point)
