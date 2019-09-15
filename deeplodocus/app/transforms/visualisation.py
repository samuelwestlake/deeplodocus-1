import numpy as np
import cv2


class Classification(object):

    def __init__(self,
                 window_name="Predictions", wait=1, scale=1, divide=1, multiply=1, plus=0, minus=0):
        self.window_name = window_name
        self.wait = wait
        self.scale = scale
        self.divide = divide
        self.multiply = multiply
        self.plus = plus
        self.minus = minus

    @staticmethod
    def __convert_to_rgb(inputs):
        return [cv2.cvtColor(i, cv2.COLOR_GRAY2RGB) for i in inputs if i.shape[2] == 1]

    @staticmethod
    def __apply_color(inputs, outputs, labels):
        _, outputs = outputs.max(1)
        for i, out, lab in zip(inputs, outputs, labels):
            if out == lab:
                i[:, :, 1] += 100
            else:
                i[:, :, 2] += 100
            i[i > 255] = 255
            i[i < 0] = 0
        return inputs

    @staticmethod
    def __extract_images(inputs):
        inputs = [i for i in inputs.cpu().numpy()]
        inputs = [np.swapaxes(i, 0, 2) for i in inputs]
        return [np.swapaxes(i, 0, 1) for i in inputs]

    @staticmethod
    def __stitch_images(inputs):
        n = len(inputs)
        h, w = inputs[0].shape[0:2]
        nx = int(np.ceil(n / 4))
        ny = int(np.ceil(n / 8))
        images = np.zeros((int(ny * h), int(nx * h), 3), np.uint8)
        k = 0
        for j in range(ny):
            for i in range(nx):
                images[j * h: (j+1) * h, i * w: (i+1) * w, :] = inputs[k]
                k += 1
                if k == len(inputs):
                    break
        return images

    def forward(self, inputs=None, outputs=None, labels=None):
        inputs = self.__transform(inputs[0])
        inputs = self.__extract_images(inputs)
        inputs = self.__convert_to_rgb(inputs)
        inputs = self.__apply_color(inputs, outputs, labels)
        images = self.__stitch_images(inputs)
        images = cv2.resize(images, (0, 0), fx=self.scale, fy=self.scale)
        cv2.imshow(self.window_name, images)
        cv2.waitKey(self.wait)
        return outputs

    def __transform(self, inputs):
        inputs += self.plus - self.minus
        inputs *= self.multiply / self.divide
        return inputs

    def finish(self):
        cv2.destroyWindow(self.window_name)