im = imread('t.bmp');
H = fspecial('disk', 200);
blurred = imfilter(im,H,'replicate'); 
imBW = im > blurred;
imBW = bwareafilt(imBW,1);
imBW = bwmorph(imBW,'close');
imSkele = bwmorph(imBW,'skel', inf);
imCross = bwmorph(imSkele,'spur', inf);
figure;imshowpair(im, imSkele)
title('Cross center overlaid on original image')