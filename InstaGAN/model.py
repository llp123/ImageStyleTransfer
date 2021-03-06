import chainer
import chainer.links as L
import chainer.functions as F
import numpy as np

from chainer import cuda,Chain,initializers
from instance_normalization_chainer.instance_normalization import InstanceNormalization

xp=cuda.cupy
cuda.get_device(0).use()


class CBR(Chain):
    def __init__(self,
                 in_ch,
                 out_ch,
                 up=False,
                 down=False,
                 predict=False,
                 activation=F.relu):

        super(CBR, self).__init__()

        w = initializers.Normal(0.02)
        self.up = up
        self.down = down
        self.activation = activation
        self.predict = predict
        with self.init_scope():
            self.cpara = L.Convolution2D(in_ch, out_ch, 3, 1, 1, initialW=w)
            self.cdown = L.Convolution2D(in_ch, out_ch, 4, 2, 1, initialW=w)

            self.bn0 = L.BatchNormalization(out_ch)
            self.in0 = InstanceNormalization(out_ch)

    def __call__(self, x):
        if x.shape[0] == 3:
            if self.up:
                h = F.unpooling_2d(x, 2, 2, 0, cover_all=False)
                h = self.activation(self.in0(self.cpara(h)))

            elif self.down:
                h = self.activation(self.in0(self.cdown(x)))

            else:
                h = self.activation(self.in0(self.cpara(x)))

        else:
            if self.up:
                h = F.unpooling_2d(x, 2, 2, 0, cover_all=False)
                h = self.activation(self.bn0(self.cpara(h)))

            elif self.down:
                h = self.activation(self.bn0(self.cdown(x)))

            else:
                h = self.activation(self.bn0(self.cpara(x)))

        return h


class ResBlock(Chain):
    def __init__(self, in_ch, out_ch):
        super(ResBlock, self).__init__()

        with self.init_scope():
            self.cbr0 = CBR(in_ch, out_ch)
            self.cbr1 = CBR(out_ch, out_ch)

    def __call__(self, x):
        h = self.cbr0(x)
        h = self.cbr1(h)

        return h + x


class Generator(Chain):
    def __init__(self, base=32, res_layers=9):
        super(Generator, self).__init__()

        res_img = chainer.ChainList()
        res_mask = chainer.ChainList()

        for _ in range(res_layers):
            res_img.add_link(ResBlock(base*4, base*4))

        for _ in range(res_layers):
            res_mask.add_link(ResBlock(base*4, base*4))

        w = initializers.Normal(0.02)
        with self.init_scope():
            self.c0_img = L.Convolution2D(3, base, 7, 1, 3, initialW=w)
            self.cbr0_img = CBR(base, base*2, down=True)
            self.cbr1_img = CBR(base*2, base*4, down=True)
            self.res_img = res_img
            self.cbr2_img = CBR(base*8, base*2, up=True)
            self.cbr3_img = CBR(base*2, base, up=True)
            self.c1_img = L.Convolution2D(base, 3, 7, 1, 3, initialW=w)

            self.bn0_img = L.BatchNormalization(base)
            self.in0_img = InstanceNormalization(base)

            self.c0_mask = L.Convolution2D(1, base, 7, 1, 3, initialW=w)
            self.cbr0_mask = CBR(base, base*2, down=True)
            self.cbr1_mask = CBR(base*2, base*4, down=True)
            self.res_mask = res_mask
            self.cbr2_mask = CBR(base*12, base*2, up=True)
            self.cbr3_mask = CBR(base*2, base, up=True)
            self.c1_mask = L.Convolution2D(base, 1, 7, 1, 3, initialW=w)

            self.bn0_mask = L.BatchNormalization(base)
            self.in0_mask = InstanceNormalization(base)

    def encode_img(self, x):
        if x.shape[0] == 3:
            h = F.relu(self.in0_img(self.c0_img(x)))
        else:
            h = F.relu(self.bn0_img(self.c0_img(x)))

        h = self.cbr0_img(h)
        h = self.cbr1_img(h)
        for link in self.res_img.children():
            h = link(h)

        return h

    def decode_img(self, x):
        h = self.cbr2_img(x)
        h = self.cbr3_img(h)
        h = self.c1_img(h)

        return F.tanh(h)

    def encode_mask(self, x):
        if x.shape[0] == 3:
            h = F.relu(self.in0_mask(self.c0_mask(x)))
        else:
            h = F.relu(self.bn0_mask(self.c0_mask(x)))

        h = self.cbr0_mask(h)
        h = self.cbr1_mask(h)
        for link in self.res_mask.children():
            h = link(h)

        return h

    def decode_mask(self, x):
        h = self.cbr2_mask(x)
        h = self.cbr3_mask(h)
        h = self.c1_mask(h)

        return F.sigmoid(h)

    def __call__(self, img, mask):
        enc_img = self.encode_img(img)
        enc_mask = self.encode_mask(mask)

        latent_img = F.concat([enc_img, enc_mask])
        latent_mask = F.concat([enc_img, enc_mask, enc_mask])

        dec_img = self.decode_img(latent_img)
        dec_mask = self.decode_mask(latent_mask)

        return dec_img, dec_mask


class Discriminator(Chain):
    def __init__(self, base=32):
        w = initializers.Normal(0.02)
        super(Discriminator, self).__init__()

        with self.init_scope():
            self.cbr0_img = CBR(3, base, down=True, activation=F.leaky_relu)
            self.cbr1_img = CBR(base, base*2, down=True, activation=F.leaky_relu)
            self.cbr2_img = CBR(base*2, base*4, down=True, activation=F.leaky_relu)

            self.cbr0_mask = CBR(1, base, down=True, activation=F.leaky_relu)
            self.cbr1_mask = CBR(base, base*2, down=True, activation=F.leaky_relu)
            self.cbr2_mask = CBR(base*2, base*4, down=True, activation=F.leaky_relu)

            self.cbr3 = CBR(base*8, base*16, down=True, activation=F.leaky_relu)
            self.cout = L.Convolution2D(base*16, 1, 3, 1, 1, initialW=w)

    def encode_img(self, x):
        h = self.cbr0_img(x)
        h = self.cbr1_img(h)
        h = self.cbr2_img(h)

        return h

    def encode_mask(self, x):
        h = self.cbr0_mask(x)
        h = self.cbr1_mask(h)
        h = self.cbr2_mask(h)

        return h

    def __call__(self, img, mask):
        enc_img = self.encode_img(img)
        enc_mask = self.encode_mask(mask)
        h = self.cbr3(F.concat([enc_img, enc_mask]))
        h = self.cout(h)

        return h
