import matplotlib.pyplot as plt
import torch.autograd as autograd
import torch
import torch
import torch.nn as nn
import numpy as np
import torch.nn.functional as F
from tqdm import tqdm
import random
from torch.optim import Adam, SGD
from spikingjelly.activation_based import (
    neuron,
    encoding,
    functional,
    surrogate,
    layer,
    monitor,
    learning,
)
def get_y_neg(y, device):
    y_neg = y.clone()
    for idx, y_samp in enumerate(y):
        allowed_indices = list(range(10))
        # print("allowed_indices:", allowed_indices)
        # print("y_samp:", y_samp.item())
        allowed_indices.remove(y_samp.item())
        y_neg[idx] = torch.tensor(allowed_indices)[
            torch.randint(len(allowed_indices), size=(1,))
        ].item()
    return y_neg.to(device)



def overlay_y_on_x(x, y, classes=10):
    """Replace the first 10 pixels of data [x] with one-hot-encoded label [y]"""
    x_ = x.clone()  # 创建一个 x 的副本，避免修改原始数据
    batch_size = x.shape[0]  # 获取批量大小
    x_[:, :, 0, :classes] *= 0.0  # 将N*C*H*W格式向量的每个样本的前10个像素值赋0
    # 遍历每个样本
    for i in range(batch_size):
        # 获取当前样本的标签
        label = y[i].item()  # y[i]是该样本的标签
        # 确保标签在0到9之间（根据设置的 classes）
        # 将第一通道前10个像素位置中对应标签的像素赋值为最大值
        x_[i, :, 0, label] = (
            x_.max()
        )  # 将每个样本前10个像素中，对应标签类别序号赋为当前矩阵最大值
    return x_
def overlay_label_on_x(x, classes=10):
    """Replace the first 10 pixels of data [x] with one-hot-encoded label [y]"""
    x_ = x.clone()  # 创建一个 x 的副本，避免修改原始数据
    batch_size = x.shape[0]  # 获取批量大小
    x_[:, :, 0, :classes] *= 0.0  # 将N*C*H*W格式向量的每个样本的前10个像素值赋0
    x_[:, :, 0, :classes] += 1
    return x_

def overlay_zero_on_x(x, y, classes=10):
    """Replace the first 10 pixels of data [x] with one-hot-encoded label [y]"""
    x_ = x.clone()  # 创建一个 x 的副本，避免修改原始数据
    batch_size = x.shape[0]  # 获取批量大小
    x_[:, :, 0, :classes] *= 0.0  # 将N*C*H*W格式向量的每个样本的前10个像素值赋0
    x_[:, :, 0, :classes] += 1.0
    # 遍历每个样本
    for i in range(batch_size):
        # 获取当前样本的标签
        label = y[i].item()  # y[i]是该样本的标签
        # 确保标签在0到9之间（根据设置的 classes）
        # 将第一通道前10个像素位置中对应标签的像素赋值为最大值
        x_[i, :, 0, label] = 0  # 将每个样本前10个像素中，对应标签类别序号赋为当前矩阵最大值
    return x_
def generate_continuous_mask(shape, block_scale=8, smooth=True, device='cpu'):
    """
    生成连续大块的二值掩码。
    参数:
        shape: [1, 1, H, W] 图像形状
        block_scale: 块的粗糙度，越大 → 块越大、越连续
        smooth: 是否使用模糊平滑
    返回:
        mask: [1, 1, H, W] 二值掩码（0或1）
    """
    B, C, H, W = shape
    # 1️⃣ 低分辨率随机噪声
    low_H, low_W = H // block_scale, W // block_scale
    noise = torch.rand((B, C, low_H, low_W), device=device)

    # 2️⃣ 上采样放大 → 产生大片区域
    mask = F.interpolate(noise, size=(H, W), mode='bilinear', align_corners=False)

    # 3️⃣ 平滑模糊（可选）
    if smooth:
        kernel = torch.ones((1, 1, 5, 5), device=device) / 25.0
        mask = F.conv2d(mask, kernel, padding=2)

    # 4️⃣ 阈值化
    threshold = random.uniform(0.4, 0.6)
    # threshold = np.random.uniform(0.4, 0.6)

    mask = (mask > threshold).float()

    return mask

def generate_negative_samples_continuous(x, y, dataset, num_classes=10, device='cpu', visualize=False,
                                         block_scale=3, smooth=False):
    """
    向量化生成负样本（保证标签对齐且不同）
    输入/输出接口保持不变：
      x: (B,1,H,W)
      y: (B,)
      dataset: MNIST dataset (dataset.data, dataset.targets) or equivalent
    返回:
      neg_samples: (B,1,H,W)
    """
    B = x.size(0)
    H, W = x.size(2), x.size(3)

    # 把dataset.targets和dataset.data准备成tensor（注意内存，MNIST可以直接放GPU；若数据很大请在CPU上索引）
    # 我把targets放device上，但 data 先保持在 cpu，再按索引一次性送到 device（避免一次性移动全部数据造成不必要内存占用）
    targets = torch.tensor(dataset.targets, device=device)  # (N,)
    data_cpu = dataset.data.float() / 255.0  # still on cpu, shape (N,28,28)

    # === 1) 为每个样本生成 neg_label，保证 != y ===
    # 用随机偏移 1..(num_classes-1)：
    offsets = torch.randint(1, num_classes, (B,), device=device)
    neg_labels = (y.to(device) + offsets) % num_classes  # shape (B,), guaranteed != y

    # === 2) 为每个 batch 位置选择一个该类别的随机索引（并保证顺序对应） ===
    neg_indices = torch.empty(B, dtype=torch.long, device=device)

    # 对每个类别挑选需要填充的位置并从该类别索引数组中随机选取
    for lbl in range(num_classes):
        pos_mask = (neg_labels == lbl)  # 哪些 batch 需要该类别样本
        cnt = int(pos_mask.sum().item())
        if cnt == 0:
            continue
        # 数据集中属于该类别的所有索引（在 cpu 上）
        class_indices_cpu = (dataset.targets == lbl).nonzero(as_tuple=True)[0]
        if len(class_indices_cpu) == 0:
            raise RuntimeError(f"No samples for class {lbl} in dataset.")
        # 在 class_indices_cpu 中随机采样 cnt 个索引（允许重复）
        sel = torch.randint(0, len(class_indices_cpu), (cnt,), device=device)
        chosen_cpu = class_indices_cpu[sel.cpu()].long()  # bring to cpu idx values
        # 将它们放到 neg_indices 的对应 batch 位置
        neg_indices[pos_mask] = chosen_cpu.to(device)

    # === 3) 用 neg_indices 在 data_cpu 上索引并转移到 device ===
    # 注意：data_cpu[neg_indices.cpu()] 得到 tensor (B, H, W) 在 cpu，再 unsqueeze -> move to device
    neg_img = data_cpu[neg_indices.cpu()].unsqueeze(1).to(device)  # (B,1,H,W)

    # === 4) 生成连续掩码（批量化）并混合 ===
    mask = generate_continuous_mask((B, 1, H, W), block_scale=block_scale, smooth=smooth, device=device)
    neg_samples = x.to(device) * mask + neg_img * (1.0 - mask)

    # === 5) 可视化（保持原先 show 行为）===
    if visualize:
        import matplotlib.pyplot as plt
        n_vis = min(3, B)
        for i in range(n_vis):
            fig, axs = plt.subplots(1, 4, figsize=(8, 2))
            axs[0].imshow(x[i].cpu().squeeze(), cmap='gray')
            axs[0].set_title(f'Positive ({int(y[i].item())})')
            axs[1].imshow(neg_img[i].cpu().squeeze(), cmap='gray')
            axs[1].set_title(f'NegClass ({int(neg_labels[i].item())})')
            axs[2].imshow(mask[i].cpu().squeeze(), cmap='gray')
            axs[2].set_title('Mask')
            axs[3].imshow(neg_samples[i].cpu().squeeze(), cmap='gray')
            axs[3].set_title('Mixed (Negative)')
            for ax in axs: ax.axis('off')
            plt.show()

    return neg_samples
def pos_derivative(x, theta):
    """
    计算 log(1 + exp(-x + theta)) 关于 x 的导数。

    参数:
        x (np.ndarray): 输入值。
        theta (float): 参数 theta。

    返回:
        np.ndarray: 导数值。
    """
    # 计算 Sigmoid 函数
    sigmoid = -1 / (1 + torch.exp(x - theta))
    
    # 返回导数
    return sigmoid
def neg_derivative(y, theta):
    """
    计算 log(1 + exp(y - theta)) 关于 y 的导数。

    参数:
        y (np.ndarray): 输入值。
        theta (float): 参数 theta。

    返回:
        np.ndarray: 导数值。
    """
    # 计算 Sigmoid 函数
    sigmoid = 1 / (1 + torch.exp(theta - y))
    
    # 返回导数
    return sigmoid


def spike_encoder(images: torch.Tensor, T: int) -> torch.Tensor:
    """
    将图像编码为 T 步脉冲序列。
    
    参数:
        images: torch.Tensor，形状为 [B, C, H, W]，像素值范围为 [0,1]
        T: int，总的时间步数
        
    返回:
        spike_train: torch.Tensor，形状为 [T, B, C, H, W]，脉冲序列（0 或 1）
    """
    B, C, H, W = images.shape
    spike_train = torch.zeros((T, B, C, H, W), device=images.device)
    v_mem = torch.zeros((B, C, H, W), device=images.device)  # 初始化膜电位为0

    for t in range(T):
        v_mem += images  # 每步累加像素值
        spike = (v_mem >= 1.0).to(torch.float)  # 触发放电
        spike_train[t] = spike
        v_mem = v_mem * (1.0 - spike)  # 膜电位重置：只有放电位置归零

    return spike_train  # 形状为 [T, B, C, H, W]

class IFNode_Non_T(neuron.IFNode):
    def neuronal_charge(self, x: torch.Tensor):
        self.v = self.v.detach() + x
class IFNode_multiple_threshold(neuron.IFNode):
    def __init__(self, v_threshold_pos: float , v_threshold_neg: float):
        super().__init__()
        self.v_threshold_pos = v_threshold_pos
        self.v_threshold_neg = v_threshold_neg
    def neuronal_fire(self):
        """
        * :ref:`API in English <BaseNode.neuronal_fire-en>`

        .. _BaseNode.neuronal_fire-cn:

        根据当前神经元的电压、阈值，计算输出脉冲。

        * :ref:`中文API <BaseNode.neuronal_fire-cn>`

        .. _BaseNode.neuronal_fire-en:


        Calculate out spikes of neurons by their current membrane potential and threshold voltage.
        """
        spike_pos = self.surrogate_function(self.v - self.v_threshold_pos)
        spike_neg = -1 * self.surrogate_function(-self.v + self.v_threshold_neg)
        return spike_pos + spike_neg
    # def forward(self, x: torch.Tensor):
    #     self.v = self.v + x
    #     pos_spike = (self.v >= self.v_threshold_pos).to(x.dtype)
    #     neg_spike = - (self.v <= self.v_threshold_neg).to(x.dtype)
    #     self.v = self.v * (1.0 - pos_spike + neg_spike)
    #     out = pos_spike + neg_spike
    #     return out

class Net(torch.nn.Module):
    def __init__(self, dims, tau, epoch, T, lr, v_threshold_pos, v_threshold_neg, opt, loss_threshold):
        super().__init__()
        self.T = T
        self.layers = []
        self.loss_threshold = loss_threshold
        self.encoder = encoding.PoissonEncoder()
        for d in range(len(dims) - 1):
            if(d==len(dims)-2):
                self.layers += nn.ModuleList(
                    [
                        OutputLayer(
                            in_features=sum(dims[1:d+1]),
                            out_features=dims[d + 1],
                            epoch=epoch,
                            T=T,
                            lr=lr,
                            v_threshold_pos=v_threshold_pos,
                            v_threshold_neg=v_threshold_neg,
                            tau=tau,
                            loss_threshold=loss_threshold,
                        ).cuda()
                    ]
                )
            elif (d==0):
                self.layers += nn.ModuleList(
                    [
                        Layer(
                            in_features=dims[d],
                            out_features=dims[d + 1],
                            epoch=epoch,
                            T=T,
                            lr=lr,
                            v_threshold_pos=v_threshold_pos + d *0.2,
                            v_threshold_neg=v_threshold_neg,
                            tau=tau,
                            loss_threshold=loss_threshold,
                        ).cuda()
                    ]
                )
            else:
                self.layers += nn.ModuleList(
                    [
                        Layer(
                            in_features=dims[d],
                            out_features=dims[d + 1],
                            epoch=epoch,
                            T=T,
                            lr=lr,
                            v_threshold_pos=v_threshold_pos + d *0.2,
                            v_threshold_neg=v_threshold_neg,
                            tau=tau,
                            loss_threshold=loss_threshold,
                        ).cuda()
                    ]
                )
    # 通过goodness计算预测结果
    def predict(self, x):
        goodness_per_label = []
        # goodness_per_label = 0  # 选择输出频率最大
        for label in range(10):
            goodness = []
            label = torch.full((x.shape[0],), label)
            h = overlay_y_on_x(x, label)
            
            # Possion编码
            # h_encoded = torch.zeros(self.T, h.shape[0], h.flatten(1).shape[1]).cuda()
            # for t in range(self.T):
            #     h_encoded[t] += self.encoder(h).flatten(1)
            # h = h_encoded
            # 频率编码
            h = spike_encoder(h, self.T)
            h = h.flatten(2)  # 将输入展平为 [T, B, C*H*W] 的形状
            spike_in_of_label = h[:,:,0:10]
            for i, layer in enumerate(self.layers):
                if i == len(self.layers) - 1:
                    break
                h = layer.predict(h)
                freq = h.mean(0)  # 计算每层的平均频率
                goodness = goodness + [layer.cal_goodness(freq).sum(1)] # 对每个样本的单层goodness求和
                h = torch.cat((h, spike_in_of_label),dim=2)
            goodness_per_label += [sum(goodness).unsqueeze(1)] # 对所有层求和优度值
        goodness_of_all_label = torch.cat(goodness_per_label, 1)# 拼接所有标签编码对应优度值
        return goodness_of_all_label.argmax(1)
        # 通过goodness计算预测结果
    def predict_winner(self, x):
        label = torch.randint(0, 10, (x.shape[0],))
        h = overlay_y_on_x(x, label)
        # 频率编码
        h = spike_encoder(x, self.T)
        h = h.flatten(2)  # 将输入展平为 [T, B, C*H*W] 的形状
        spike_in_of_label = h[:,:,0:10]
        spike_in_of_output_layer = torch.empty((h.shape[0],h.shape[1],0)).cuda()
        # spike_in_of_output_layer = torch.cat((spike_in_of_output_layer,h),dim=2)
        spike_in_of_output_layer = torch.cat((spike_in_of_output_layer,spike_in_of_label),dim=2)
        for i, layer in enumerate(self.layers):
            if i == len(self.layers) - 1:
                spike_out = layer.predict(spike_in_of_output_layer) 
            else:
                h = layer.predict(h)
                spike_in_of_output_layer = torch.cat((spike_in_of_output_layer,h),dim=2)
                h = torch.cat((h,spike_in_of_label),dim=2)
        spike_out_sum = spike_out.sum(0)  # 计算输出层的总脉冲
        return spike_out_sum.argmax(1)
    def predict_analyze(self, x):
        goodness_per_label = []
        goodness_label_layer_goodness = torch.zeros(10,len(self.layers),x.shape[0]).cuda()
        freq_label_layer_freq = torch.zeros(10,len(self.layers),x.shape[0],1000).cuda()
        for label in range(10):
            goodness = []
            label = torch.full((x.shape[0],), label)
            h = overlay_y_on_x(x, label)
            # 频率编码
            h = spike_encoder(h, self.T)
            h = h.flatten(2)  # 将输入展平为 [T, B, C*H*W] 的形状
            spike_in_of_label = h[:,:,0:10]
            for i, layer in enumerate(self.layers):
                if i == len(self.layers) - 1:
                    break
                h = layer.predict(h)
                freq = h.mean(0)  # 计算每层的平均频率
                goodness = goodness + [layer.cal_goodness(freq).sum(1)] # 对每个样本的单层goodness求和
                goodness_label_layer_goodness[label,i,:] = layer.cal_goodness(freq).sum(1)
                freq_label_layer_freq[label,i,:,0:freq.shape[1]] = freq
                h = torch.cat((h, spike_in_of_label),dim=2)
            goodness_per_label += [sum(goodness).unsqueeze(1)] # 对所有层求和优度值
        goodness_of_all_label = torch.cat(goodness_per_label, 1)# 拼接所有标签编码对应优度值
        return goodness_of_all_label.argmax(1),goodness_label_layer_goodness.cpu(),freq_label_layer_freq
    def train(self, x_pos, x_neg, y, layer_idx):
        h_pos, h_neg = x_pos, x_neg
        for i, layer in enumerate(self.layers):
            if i == layer_idx:
                train_mode = True
                h_pos, h_neg, loss = layer.train(h_pos, h_neg, y, train_mode)
                break
            else:
                train_mode = False
                h_pos, h_neg, loss = layer.train(h_pos, h_neg, y, train_mode)
        return loss
    def train_ff_stdp(self, x_pos, x_neg, label):
        x_pos_encoded = spike_encoder(x_pos, self.T)
        x_neg_encoded = spike_encoder(x_neg, self.T)
        in_pos = x_pos_encoded.flatten(2)
        in_neg = x_neg_encoded.flatten(2)

        # in_pos = torch.zeros(self.T, x_pos.shape[0], x_pos.flatten(1).shape[1]).cuda()
        # in_neg = torch.zeros(self.T, x_pos.shape[0], x_neg.flatten(1).shape[1]).cuda()
        # for t in range(self.T):
        #     x_pos_encoded = self.encoder(x_pos)
        #     x_neg_encoded = self.encoder(x_neg)
        #     in_pos[t] += x_pos_encoded.flatten(1)
        #     in_neg[t] += x_neg_encoded.flatten(1)

        spike_input_pos = in_pos
        spike_input_neg = in_neg

        goodness_pos, cos_pos, spike_out_pos = self.train_ff_stdp_step(spike_input_pos, True, label)
        goodness_neg, cos_neg, spike_out_neg = self.train_ff_stdp_step(spike_input_neg, False, label)
        
        return goodness_pos, goodness_neg, cos_pos, cos_neg
    def train_ff_stdp_step(self, input, is_pos, label):
        spike_input  = input
        goodness_per_layer = []
        cos_sim_per_layer = []
        spike_in_of_label = spike_input[:,:,0:10]
        spike_in_of_output_layer = torch.empty((spike_input.shape[0],spike_input.shape[1],0)).cuda()
        spike_in_of_output_layer = torch.cat((spike_in_of_output_layer,spike_input[:,:,0:10]),dim=2)
        # spike_in_of_output_layer = torch.cat((spike_in_of_output_layer,spike_input),dim=2)
        for i, layer in enumerate(self.layers):
            if i == len(self.layers) - 1:
                spike_output = layer.train_bp_stdp(spike_in_of_output_layer, label)
            else:
                spike_input, g ,cos_sim = layer.train_ff_stdp(spike_input, is_pos)
                goodness_per_layer.append(g.mean().item())
                cos_sim_per_layer.append(cos_sim)
                spike_in_of_output_layer = torch.cat((spike_in_of_output_layer,spike_input),dim=2)
                spike_input = torch.cat((spike_input,spike_in_of_label),dim=2)
        return goodness_per_layer, cos_sim_per_layer , spike_output

    def save(self, args, path):
        check_point = {
            "net": {
                f"layer_{i}": layer.state_dict() for i, layer in enumerate(self.layers)
            },
            "args": args,
        }
        torch.save(check_point, path)

    def load(self, path):
        check_point = torch.load(path)
        # 加载每一层的参数
        for i, layer in enumerate(self.layers):
            layer.load_state_dict(check_point["net"][f"layer_{i}"])
        # 打印加载的超参数
        print(check_point["args"])


class Layer(nn.Module):
    def __init__(
        self, in_features, out_features, epoch, T, lr, v_threshold_pos, v_threshold_neg, tau, loss_threshold
    ):
        super().__init__()
        self.layer = nn.Sequential(
            layer.Flatten(),
            layer.Linear(in_features, out_features, bias=False),
            # neuron.LIFNode(tau=tau, v_threshold= v_threshold, surrogate_function=surrogate.ATan())
            # IFNode_Non_T(v_reset= None, v_threshold= v_threshold, surrogate_function=surrogate.ATan(), step_mode='s')
            neuron.IFNode(
                v_reset=None,
                v_threshold=v_threshold_pos,
                surrogate_function=surrogate.ATan(),
                step_mode="s",
            ),
            # IFNode_multiple_threshold(
            #     v_threshold_pos=v_threshold_pos,
            #     v_threshold_neg=v_threshold_neg
            # ),
        )
        self.lr = lr
        self.spike_input_rate = 0
        self.in_features = in_features
        self.out_features = out_features
        self.num_epochs = epoch
        self.T = T
        self.threshold = loss_threshold
        self.encoder = encoding.PoissonEncoder()
        self.opt = Adam(self.parameters(), lr=lr)
        # self.opt = SGD(self.parameters(), lr=lr, momentum=0.9, weight_decay=1e-4)
        self.visible = False
        self.spike_vis = torch.zeros(out_features).unsqueeze(1)
    def initialize(self):  # 初始化模型参数
        for m in self.modules():
            if isinstance(m, nn.Linear):
                # 使用正态分布初始化权重，并添加一个正偏置
                nn.init.normal_(m.weight.data, std=np.sqrt(2 / self.out_features))
                m.weight.data += 0.1  # 添加正偏置，确保权重平均值大于 0


    def visualize_spike_in_timestep(self, layer_forward_out):
        self.spike_vis = torch.cat(
            (self.spike_vis, layer_forward_out[0].cpu().flatten().unsqueeze(1)), dim=1
        )
        if self.visible and self.spike_vis.shape[1] == self.T:
            plt.imshow(
                self.spike_vis.detach().numpy(), cmap="viridis", aspect="auto"
            )  # 使用 'viridis' 颜色映射，自动调整纵横比
            plt.colorbar(label="Spike Intensity")  # 添加颜色条并标注
            plt.title("Spike Visualization")  # 图像标题
            plt.xlabel("Time Steps")  # x 轴标签
            plt.ylabel("Neuron Index")  # y 轴标签
            plt.tight_layout()  # 自动调整子图参数
            plt.show()
        if self.spike_vis.shape[1] == self.T:
            self.spike_vis = torch.zeros(self.out_features).unsqueeze(1)

    def cal_goodness(self, freq):
        # goodness = self.T * freq.pow(2)
        goodness = self.T * freq.abs().pow(2) * freq.sign()
        return goodness

    def forward(self, x):
        # 对第1维度（通道维度）计算L2范数，然后进行归一化
        # x_direction = x / (x.norm(2, 1, keepdim=True) + 1e-4)
        return self.layer(x)

    def train(self, x_pos, x_neg, y, train_mode):
        g_pos = torch.zeros(self.T, x_pos.shape[0], self.out_features).cuda()
        g_neg = torch.zeros(self.T, x_pos.shape[0], self.out_features).cuda()
        in_pos = torch.zeros(self.T, x_pos.shape[0], self.in_features).cuda()
        in_neg = torch.zeros(self.T, x_pos.shape[0], self.in_features).cuda()
        for t in range(self.T):
            x_pos_encoded = self.encoder(x_pos)
            x_neg_encoded = self.encoder(x_neg)
            g_pos[t] += self.forward(x_pos_encoded)
            in_pos[t] += x_pos_encoded.flatten(1)
            g_neg[t] += self.forward(x_neg_encoded)
            in_neg[t] += x_neg_encoded.flatten(1)
        g_pos_freq = g_pos.mean(0)
        g_neg_freq = g_neg.mean(0)
        if train_mode:
            self.opt.zero_grad()
            pos_goodness = self.cal_goodness(g_pos_freq)
            neg_goodness = self.cal_goodness(g_neg_freq)
            loss = torch.log(
                1
                + torch.exp(
                    torch.cat(
                        [-pos_goodness + self.threshold, neg_goodness - self.threshold]
                    )
                )
            ).mean()
            # loss = torch.log(1 + torch.exp(-pos_goodness + neg_goodness + self.threshold)).mean()
            loss.backward()
            # grad_w_autograd = self.layer[1].weight.grad.clone()
            # loss, grad = Custom_Loss.Frequency_FF_Loss(g_pos,g_neg,in_pos,in_neg,self.in_features, self.out_features, self.T, self.threshold, x_pos, x_neg, g_pos_freq, g_neg_freq)
            # for param in self.layer.parameters():
            #     if param.requires_grad:
            #         # 使用优化器更新权重
            #         param.grad = grad
            # grad_w_manual = grad.clone()
            # cos_sim = torch.nn.functional.cosine_similarity(grad_w_manual.view(-1), grad_w_autograd.view(-1), dim=0)
            # print(cos_sim)
            # print("手写梯度均值:", grad_w_manual.mean().item(), "标准差:", grad_w_manual.std().item())
            # print("自动梯度均值:", grad_w_autograd.mean().item(), "标准差:", grad_w_autograd.std().item())
            self.opt.step()
            functional.reset_net(self.layer)
            return g_pos_freq.detach(), g_neg_freq.detach(), loss.cpu().item()
        else:
            functional.reset_net(self.layer)
            return g_pos_freq.detach(), g_neg_freq.detach(), 0
    def train_ff_stdp(self,x_encoded,is_pos):
        N = x_encoded.shape[1]
        input_spike_sum = x_encoded.sum(0)
        output_spike = torch.zeros(self.T, N, self.out_features).cuda()
        for t in range(self.T):
            output_spike[t] += self.forward(x_encoded[t])
        out_freq = output_spike.mean(0).transpose(0,1)
        self.opt.zero_grad()
        goodness = self.cal_goodness(out_freq)

        if is_pos:
            L_to_s_grad = 2*out_freq*pos_derivative(goodness,self.threshold)
            loss = torch.log(1 + torch.exp(-goodness + self.threshold)).mean()
        else:
            L_to_s_grad = 2*out_freq*neg_derivative(goodness,self.threshold)
            loss = torch.log(1 + torch.exp(goodness - self.threshold)).mean()
        weight_grad = -1 * L_to_s_grad @ input_spike_sum / N
        # weight_grad = -1 * torch.mean(L_to_s_grad,dim=1,keepdim=True) @ torch.mean(input_spike_sum,dim=0,keepdim=True)
        loss.backward()
        with torch.no_grad():
            for param in self.layer.parameters():
                    # 使用优化器更新权重           
                    param += self.lr * weight_grad
                    cos_sim = torch.cosine_similarity(param.grad.flatten(),-1*weight_grad.flatten(),dim=0)
                    # param.grad = weight_grad
                    # plt.imshow(np.array(param[511].cpu().reshape(28,28)))
                    # 可视化梯度分布
                    # plt.figure(figsize=(8, 6))
                    # plt.hist(param.grad.cpu().numpy().flatten(), bins=50, color='blue', alpha=0.7)
                    # plt.title("Gradient Distribution")
                    # plt.xlabel("Gradient Value")
                    # plt.ylabel("Frequency")
                    # plt.grid(True)
                    # plt.show()
                    # param.clamp_(min=-12.0, max=12.0)  # 限制权重在[-12, 12]范围内
        # self.opt.step()
        functional.reset_net(self.layer)
        return output_spike.detach(), goodness.detach().mean(1).cpu(),cos_sim.detach().cpu().item()
    def predict(self, x):
        h = x
        g = torch.zeros(self.T, x.shape[1], self.out_features).cuda()
        # self.spike_input_rate = 0
        # h_encoded = spike_encoder(h, self.T)
        for t in range(self.T):
            # h_encoded = self.encoder(h)
            # self.spike_input_rate += h_encoded.mean().detach().cpu() / self.T
            spike_out = self.forward(h[t])
            g[t] += spike_out
            # 用于观察输出层脉冲发放情况
            # if (self.out_features==10):
            # if(g[0].sum() > 0):
            # print(1)
            # self.visualize_spike_in_timestep(spike_out)
        functional.reset_net(self.layer)
        return g
class OutputLayer(nn.Module):
    def __init__(
        self, in_features, out_features, epoch, T, lr, v_threshold_pos, v_threshold_neg, tau, loss_threshold
    ):
        super().__init__()
        self.layer = nn.Sequential(
            layer.Flatten(),
            layer.Linear(in_features, out_features, bias=False),
            # neuron.IFNode(
            #     v_reset=None,
            #     v_threshold=v_threshold_pos,
            #     surrogate_function=surrogate.ATan(),
            #     step_mode="s",
            # ),
            IFNode_multiple_threshold(
                v_threshold_pos=v_threshold_pos,
                v_threshold_neg=v_threshold_neg
            ),
        )
        self.lr = lr
        self.spike_input_rate = 0
        self.in_features = in_features
        self.out_features = out_features
        self.num_epochs = epoch
        self.T = T
        self.threshold = loss_threshold
        self.encoder = encoding.PoissonEncoder()
        self.opt = Adam(self.parameters(), lr=lr)
        # self.opt = SGD(self.parameters(), lr=lr, momentum=0.9, weight_decay=1e-4)
        self.visible = False
        self.spike_vis = torch.zeros(out_features).unsqueeze(1)
    def forward(self, x):
        # 对第1维度（通道维度）计算L2范数，然后进行归一化
        # x_direction = x / (x.norm(2, 1, keepdim=True) + 1e-4)
        return self.layer(x)
    def train_bp_stdp(self,x_encoded, label):
        N = x_encoded.shape[1]
        input_spike_sum = x_encoded.sum(0).cuda()
        output_spike = torch.zeros(self.T, N, self.out_features).cuda()
        ksi_output = torch.zeros(N,self.out_features).cuda() 
        for t in range(self.T):
            output_spike[t] += self.forward(x_encoded[t])
        spike_sums = output_spike.sum(0)  # 对时间维度求和，形状为 [N, out_features]
         # 创建一个布尔掩码，判断每个样本的每个输出神经元是否满足条件
        neg_mask = (spike_sums >= 1) & (torch.arange(self.out_features).cuda() != label.unsqueeze(1))
        pos_mask = (spike_sums <= (self.T/2)) & (torch.arange(self.out_features).cuda() == label.unsqueeze(1))
        ksi_output[pos_mask] = 1
        ksi_output[neg_mask] = -1
        ksi_output = ksi_output.transpose(0,1)
        self.opt.zero_grad()
        weight_grad = ksi_output @ input_spike_sum / N
        with torch.no_grad():
            for param in self.layer.parameters():
                    # 使用优化器更新权重           
                    param += self.lr * weight_grad
        functional.reset_net(self.layer)
        return output_spike.detach()
    def predict(self, x):
        h = x
        g = torch.zeros(self.T, x.shape[1], self.out_features).cuda()
        for t in range(self.T):
            spike_out = self.forward(h[t])
            g[t] += spike_out
        functional.reset_net(self.layer)
        return g