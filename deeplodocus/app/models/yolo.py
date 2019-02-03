import torch
import torch.nn as nn

from deeplodocus.utils.generic_utils import get_specific_module
from deeplodocus.app.layers.empty import EmptyLayer


class YOLOv3(nn.Module):

    def __init__(
            self,
            backbone=None,
            num_classes=80,
            skip_layers=(36, 61),
            image_shape=(256, 256),
            anchors=(
                ((116, 90), (156, 198), (373, 326)),
                ((30, 61), (62, 45), (59, 119)),
                ((10, 13), (16, 30), (22, 23))
            ),
    ):
        super(YOLOv3, self).__init__()
        if backbone is None:
            backbone = {
                "name": "Daknet53",
                "module": "deeplodocus.app.models.darknet",
                "kwargs": {
                    "num_channels": 3,
                    "include_top": False
                }
            }
        num_anchors = len(anchors)
        backbone_module = get_specific_module(name=backbone["name"], module=backbone["module"], fatal=True)
        self.backbone = backbone_module(**backbone["kwargs"])
        self.skip_layers = skip_layers

        # CONVOLUTIONAL LAYERS/BLOCKS
        self.conv_1_1 = ConvLayer(in_channels=1024, out_channels=512, kernel_size=1, negative_slope=0.1)
        self.conv_1_2 = ConvBlock(1024)
        self.conv_1_3 = ConvLayer(in_channels=512, out_channels=1024, kernel_size=3, padding=1, negative_slope=0.1)
        self.conv_1_4 = nn.Conv2d(in_channels=1024, out_channels=num_anchors * (num_classes + 5), kernel_size=1)

        self.conv_2_1 = ConvLayer(in_channels=512, out_channels=256, kernel_size=1, negative_slope=0.1)
        self.conv_2_2 = ConvLayer(in_channels=768, out_channels=256, kernel_size=1, negative_slope=0.1)
        self.conv_2_3 = ConvBlock(512)
        self.conv_2_4 = ConvLayer(in_channels=256, out_channels=512, kernel_size=3, padding=1, negative_slope=0.1)
        self.conv_2_5 = nn.Conv2d(in_channels=512, out_channels=num_anchors * (num_classes + 5), kernel_size=1)

        self.conv_3_1 = ConvLayer(in_channels=256, out_channels=128, kernel_size=1, negative_slope=0.1)
        self.conv_3_2 = ConvLayer(in_channels=384, out_channels=128, kernel_size=1, negative_slope=0.1)
        self.conv_3_3 = ConvBlock(256)
        self.conv_3_4 = ConvLayer(in_channels=128, out_channels=256, kernel_size=3, padding=1, negative_slope=0.1)
        self.conv_3_5 = nn.Conv2d(in_channels=256, out_channels=num_anchors * (num_classes + 5), kernel_size=1)

        # UPSAMPLE LAYER
        self.upsample = nn.Upsample(scale_factor=2, mode="nearest")

        # YOLO LAYERS
        self.yolo_layer_1 = YoloLayer(
            num_classes=num_classes,
            image_shape=image_shape,
            anchors=anchors[0]
        )
        self.yolo_layer_2 = YoloLayer(
            num_classes=num_classes,
            image_shape=image_shape,
            anchors=anchors[1]
        )
        self.yolo_layer_3 = YoloLayer(
            num_classes=num_classes,
            image_shape=image_shape,
            anchors=anchors[2]
        )

    def forward(self, x):
        x = self.backbone(x)                                            # b x 1024 x h/32 x w/32
        x = self.conv_1_1(x)                                            # b x 512 x h/32 x w/32
        x = self.conv_1_2(x)                                            # b x 512 x h/32 x w/32
        output_1 = self.conv_1_3(x)                                     # b x 1024 x h/32 x w/32
        output_1 = self.conv_1_4(output_1)                              # b x 255 x h/32 x w/32
        output_1 = self.yolo_layer_1(output_1)                          # First YOLO layer

        x = self.conv_2_1(x)                                            #
        x = self.upsample(x)                                            # b x 256 x h/12 x w/16
        x = torch.cat((x, self.backbone.skip[self.skip_layers[1]]), 1)  # Concatenate x with second backbone skip layer
        x = self.conv_2_2(x)
        x = self.conv_2_3(x)
        output_2 = self.conv_2_4(x)
        output_2 = self.conv_2_5(output_2)
        output_2 = self.yolo_layer_2(output_2)

        x = self.conv_3_1(x)
        x = self.upsample(x)
        x = torch.cat((x, self.backbone.skip[self.skip_layers[0]]), 1)
        x = self.conv_3_2(x)
        x = self.conv_3_3(x)
        output_3 = self.conv_3_4(x)
        output_3 = self.conv_3_5(output_3)
        output_3 = self.yolo_layer_3(output_3)

        return torch.cat((output_1, output_2, output_3), 1)


class ConvBlock(nn.Module):

    def __init__(self, filters=1024, negative_slope=0.1):
        super(ConvBlock, self).__init__()
        self.conv_1 = ConvLayer(
            in_channels=int(filters / 2),
            out_channels=filters,
            kernel_size=3,
            padding=1,
            negative_slope=negative_slope
        )
        self.conv_2 = ConvLayer(
            in_channels=filters,
            out_channels=int(filters / 2),
            kernel_size=1,
            negative_slope=negative_slope
        )
        self.conv_3 = ConvLayer(
            in_channels=int(filters / 2),
            out_channels=filters,
            kernel_size=3,
            padding=1,
            negative_slope=negative_slope
        )
        self.conv_4 = ConvLayer(
            in_channels=filters,
            out_channels=int(filters / 2),
            kernel_size=1,
            negative_slope=negative_slope
        )

    def forward(self, x):
        x = self.conv_1(x)
        x = self.conv_2(x)
        x = self.conv_3(x)
        x = self.conv_4(x)
        return x


class ConvLayer(nn.Module):

    def __init__(
            self, in_channels, out_channels,
            kernel_size=3,
            bias=False,
            stride=1,
            batch_norm=True,
            padding=0,
            negative_slope=0.0
    ):
        super(ConvLayer, self).__init__()
        self.conv_layer = nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            bias=bias,
            stride=stride,
            padding=padding
        )
        if batch_norm:
            self.norm_layer = nn.BatchNorm2d(out_channels)
        else:
            self.norm_layer = EmptyLayer()
        if negative_slope == 0:
            self.activation_layer = nn.ReLU()
        else:
            self.activation_layer = nn.LeakyReLU(negative_slope=negative_slope)

    def forward(self, x):
        x = self.conv_layer(x)
        x = self.norm_layer(x)
        x = self.activation_layer(x)
        return x


class YoloLayer(nn.Module):

    def __init__(self, anchors, num_classes, image_shape, num_anchors=3):
        super(YoloLayer, self).__init__()
        self.num_classes = num_classes
        self.num_anchors = len(anchors)
        self.image_shape = image_shape      # (height, width)
        self.num_anchors = num_anchors
        self.anchors = anchors
        self.num_classes = num_classes

    def forward(self, x):
        device = torch.device(x.device)
        batch_size, _, input_height, input_width = x.shape
        stride = (
            self.image_shape[0] / input_height,
            self.image_shape[1] / input_width
        )
        prediction = x.view(
            batch_size,
            self.num_anchors,
            self.num_classes + 5,
            input_height,
            input_width
        ).permute(0, 1, 3, 4, 2).contiguous()
        # Outputs
        x = torch.sigmoid(prediction[..., 0])
        y = torch.sigmoid(prediction[..., 1])
        w = prediction[..., 2]
        h = prediction[..., 3]
        obj = prediction[..., 4]
        cls = prediction[..., 5:]

        # Calculate offsets
        grid_x = torch.arange(input_width).repeat(input_height, 1).view([1, 1, input_height, input_width]).type(torch.FloatTensor).to(device)
        grid_y = torch.arange(input_height).repeat(input_width, 1).t().view([1, 1, input_height, input_width]).type(torch.FloatTensor).to(device)
        scaled_anchors = torch.tensor([(a_w / stride[1], a_h / stride[0]) for a_w, a_h in self.anchors]).type(torch.FloatTensor).to(device)
        anchor_w = scaled_anchors[:, 0:1].view((1, self.num_anchors, 1, 1))
        anchor_h = scaled_anchors[:, 1:2].view((1, self.num_anchors, 1, 1))

        # Add offset and scale with anchors
        boxes = torch.FloatTensor(prediction[..., :4].shape).to(device)

        boxes[..., 0] = x.data + grid_x
        boxes[..., 1] = y.data + grid_y
        boxes[..., 2] = torch.exp(w.data) * anchor_w
        boxes[..., 3] = torch.exp(h.data) * anchor_h

        output = torch.cat(
            (
                boxes.view(batch_size, -1, 4) * stride[0],  # stride is now a vector!!
                obj.view(batch_size, -1, 1),
                cls.view(batch_size, -1, self.num_classes),
            ),
            -1,
        )
        return output


if __name__ == "__main__":
    from deeplodocus.app.models.darknet import Darknet53

    darknet53 = Darknet53(include_top=False)
    yolo = YOLOv3(backbone=darknet53)
    print(yolo)