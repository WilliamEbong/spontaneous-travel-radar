# Art

`limb-1800.jpg`, `limb-960.jpg`: the first frame's photograph. "Night limb with city lights, from the ISS", NASA /
Rick Mastracchio, public domain (NASA, no US copyright); catalogue id `nasa-49` in the archive-of-looking library.
Cropped to rows 420 to 1703 of the 2560 x 1703 library file (the station hardware at the top edge removed), the sky
extended upward with the photograph's own sky colour (0x0d0307, sampled from rows 440 to 520) so the limb sits at 63.3%
of the image, then graded with the skill's recipe (blacks lifted, whites rolled to ivory, 15% less saturation, fine grain, soft
vignette) and resized to 1800 and 960 px wide:

```
ffmpeg -i nasa-49.jpg -vf "crop=2560:1283:0:420,pad=2560:2676:0:1393:color=0x0d0307,scale=1800:-1,curves=r='0/0.06 0.75/0.76 1/0.95':g='0/0.05 0.75/0.75 1/0.935':b='0/0.06 0.75/0.75 1/0.9',eq=saturation=0.85,noise=alls=5:allf=t,vignette=PI/10" -update 1 -q:v 4 limb-1800.jpg
```

The limb sits at 63.3% of the image's height, so `object-position: 42% 63.3%` (`.frame-art img` in `site/style.css`)
lands it on the page's horizon at any viewport aspect.
