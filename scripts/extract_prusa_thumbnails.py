
#
import re
import base64

dir = "/home/pi/sdcard/"
file = "square_tower_0.2mm_PLA_ENDER3_46m.gcode"
#f = f.open(file, 'r')

thumbnails = []
cur_thumbnail = {}
state = 0
with open(dir + file, 'r') as f:
    for line in f:
        if state == 0:
            match = re.match(r'^; thumbnail begin ([0-9]+)x([0-9]+) ([0-9]+)', line)
            if match:
                cur_thumbnail = {
                    "width": match.group(1),
                    "height": match.group(2),
                    "size": match.group(3),
                    "data": ""
                }
                state = 1
                continue
        elif state == 1:
            if re.match (r'^; thumbnail end', line):
                state = 0
                thumbnails.append(cur_thumbnail)
                continue
            match = re.match(r'^; (\S+)$', line)
            if match:
                cur_thumbnail['data'] += match.group(1)

if len(thumbnails) > 0:
    biggest = 0
    for i in range(len(thumbnails)):
        if i == 0:
            continue
        if thumbnails[i]['width'] > thumbnails[biggest]['width']:
            biggest = i

    image = base64.decodestring(thumbnails[biggest]['data'])
    name = file.split('.gcod')[0] + ".png"
    f = open(dir + name, 'wb')
    f.write(image)
    f.close()
