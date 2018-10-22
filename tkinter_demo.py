import tkinter as tk
import numpy as np
import random
from PIL import Image, ImageTk

dragged_item = None
current_coords = 0, 0
width = 1280
height = 960
scale = 1.0
base = 0

def start_drag(event):
    global current_coords
    global dragged_item
    result = canvas.find_withtag('current')
    if result:
        dragged_item = result[0]
        current_coords = canvas.canvasx(event.x), canvas.canvasy(event.y)
    else:
        dragged_item = 'all'
        current_coords = canvas.canvasx(event.x), canvas.canvasy(event.y)

def stop_drag(event):
    global pos_list
    global current_coords
    global dragged_item
    global base
    try:
        print dragged_item-1-base
        pos_list[dragged_item-1-base] = (current_coords[0], current_coords[1])
    except Exception as e:
        print e
    dragged_item = None

def drag(event):
    global current_coords
    xc, yc = canvas.canvasx(event.x), canvas.canvasy(event.y)
    dx, dy = xc - current_coords[0], yc - current_coords[1]
    current_coords = xc, yc
    canvas.move(dragged_item, dx, dy)

def zoomer(event):
    global scale
    if event.delta == 120:
        if scale < 2**5:
            scale *= 1.25
    elif event.delta  == -120:
        if scale > 0.5**5:
            scale *= 0.75
    redraw(event.x, event.y)

def redraw(x=0, y=0):
    global scale
    global base
    base += 10
    iw, ih = img_list[0].size
    size = int(iw * scale), int(ih * scale)
    canvas.delete('all')
    for i in range(10):
        tk_list[i] = ImageTk.PhotoImage(img_list[i].resize((size[0], size[1])))
        canvas.create_image(pos_list[i][0], pos_list[i][1], image=tk_list[i], anchor='nw')
    canvas.scale('all', x, y, scale, scale)

# --------------------------------------------------------------------------------------------------

img_list, tk_list, pos_list = [], [], []
for i in range(10):
    img_list.append(Image.open('../img/%s.png'%i).resize((120,120)))
    pos_list.append((random.randint(0,width), random.randint(0,height)))

background_data = np.ones((height, width))
background_data[:, :] = 255 * np.ones((height, width))
background_data = np.array(background_data, dtype='uint8')
pil_image_bg = Image.fromarray(background_data)

root = tk.Tk()
for i in range(10):
    tk_list.append(ImageTk.PhotoImage(img_list[i]))

canvas = tk.Canvas(root, width=width, height=height)
canvas.pack()
canvas.bind('<ButtonPress-1>', start_drag)
canvas.bind('<ButtonRelease-1>', stop_drag)
canvas.bind('<B1-Motion>', drag)
canvas.bind_all('<MouseWheel>', zoomer)

for i in range(10):
    canvas.create_image(pos_list[i][0], pos_list[i][1], image=tk_list[i], anchor='nw')

root.mainloop()