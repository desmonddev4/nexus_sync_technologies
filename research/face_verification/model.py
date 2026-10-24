"""Small face embedding CNN initialized and trained from scratch for research only."""
import torch
from torch import nn
from torch.nn import functional as F


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int = 1):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.PReLU(out_channels),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
        )
        self.skip = (nn.Identity() if stride == 1 and in_channels == out_channels else
                     nn.Sequential(nn.Conv2d(in_channels, out_channels, 1, stride=stride, bias=False),
                                   nn.BatchNorm2d(out_channels)))
        self.activation = nn.PReLU(out_channels)

    def forward(self, x):
        return self.activation(self.layers(x) + self.skip(x))


class FaceEmbeddingNet(nn.Module):
    """Maps a normalized 112x112 RGB face crop to a unit-length 128-D vector."""
    def __init__(self, embedding_size: int = 128):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1, bias=False), nn.BatchNorm2d(32), nn.PReLU(32),
            ConvBlock(32, 32), ConvBlock(32, 64, stride=2),
            ConvBlock(64, 64), ConvBlock(64, 128, stride=2),
            ConvBlock(128, 128), ConvBlock(128, 256, stride=2),
            ConvBlock(256, 256), nn.AdaptiveAvgPool2d(1), nn.Flatten(),
        )
        self.projection = nn.Linear(256, embedding_size, bias=False)
        self.embedding_norm = nn.LayerNorm(embedding_size)

    def forward(self, images):
        return F.normalize(self.embedding_norm(self.projection(self.features(images))), p=2, dim=1)


class AngularMarginHead(nn.Module):
    """ArcFace-style classification head used only while training identity embeddings."""
    def __init__(self, embedding_size: int, class_count: int, scale: float = 32.0, margin: float = 0.35):
        super().__init__()
        if class_count < 2:
            raise ValueError("At least two training identities are required")
        self.weight = nn.Parameter(torch.empty(class_count, embedding_size))
        nn.init.xavier_uniform_(self.weight)
        self.scale = scale
        self.margin = margin

    def forward(self, embeddings, labels):
        cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
        cosine = cosine.clamp(-1 + 1e-7, 1 - 1e-7)
        sine = torch.sqrt((1.0 - cosine.square()).clamp_min(1e-7))
        phi = cosine * torch.cos(torch.tensor(self.margin, device=cosine.device)) - sine * torch.sin(torch.tensor(self.margin, device=cosine.device))
        one_hot = F.one_hot(labels, num_classes=self.weight.shape[0]).to(dtype=cosine.dtype)
        return (one_hot * phi + (1.0 - one_hot) * cosine) * self.scale

