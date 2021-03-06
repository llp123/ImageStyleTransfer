# RelGAN
## Summary
- RelGAN is different to existing many-to-many conversion such as StarGAN with respect to enabling us to interpolate source image and target image.
- The authors of this paper propose discriminator which predicts alpha, interpolation rate

## Usage

### Training Phase
Execute the command line below.
```bash
$ python train.py --path <IMG_PATH>
```

`IMG_PATH` is a directory which contains training images.
I assume the path structure of `IMG_PATH` below.

```
IMG_PATH - dir1 - file1
                - file2
                - ...
                
         - dir2 - file1
                - file2
                - ...
                
         - dir3 - file1
                - file2
                - ...
         - ...
```

## Result
Result image generated by my development environment is as follows.

![RelGAN](https://github.com/SerialLain3170/ImageStyleTransfer/blob/master/RelGAN/RelGAN_result.jpg)

- Batch size: 16
- Optimizer: Adam(α=0.00005, β1=0.9)
- The weight of interpolation loss, cycle-consistency loss and self-reconstruction loss is 10.0.
- I don't use orthogonal regulrization described in paper. Instead, I use zero-gradient penalty.
