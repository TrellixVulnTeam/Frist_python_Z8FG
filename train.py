#!/usr/bin/python
# -*- coding: UTF-8 -*-
#个人微信 wibrce
#Author 杨博
import numpy as np
import torch
import torch.nn as nn
import utils
import torch.nn.functional as F
from sklearn import metrics
import time
from pytorch_pretrained.optimization import  BertAdam

def train(config, model, train_iter, dev_iter, test_iter):
    """
    模型训练方法
    :param config:
    :param model:
    :param train_iter:
    :param dev_iter:
    :param test_iter:
    :return:
    """
    start_time = time.time()  #训练开始时间
    #启动 BatchNormalization 和 dropout
    model.train()
    #拿到所有mode种的参数
    param_optimizer = list(model.named_parameters())
    # 不需要衰减的参数
    no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']

    optimizer_grouped_parameters = [
        {'params':[p for n,p in param_optimizer  if not any( nd in n for nd in no_decay)], 'weight_decay':0.01},
        {'params':[p for n,p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_deacy':0.0}
    ]

    optimizer = BertAdam(params = optimizer_grouped_parameters,
                         lr=config.learning_rate,
                         warmup=0.05,
                         t_total=len(train_iter) * config.num_epochs)

    total_batch = 0 #记录进行多少batch
    dev_best_loss = float('inf') #记录校验集合最好的loss
    last_imporve = 0 #记录上次校验集loss下降的batch数
    flag = False #记录是否很久没有效果提升，停止训练
    model.train()#开启训练模式
    for epoch in range(config.num_epochs):
        print('Epoch [{}/{}'.format(epoch+1, config.num_epochs))
        # trains：[ids,len_q,mask]   labels：128     train_iter：[ids,labels,len_q,mask]
        # 顺序对不上是因为，对可迭代对象使用for in时，会自动调用该对象的__next()__，而在该方法中，改变了该对象的数据顺序
        for i, (trains, labels) in enumerate(train_iter):
            outputs = model(trains)
            model.zero_grad() #梯度是累计的，下一个循环计算梯度之前先清零
            loss = F.cross_entropy(outputs, labels)
            loss.backward(retain_graph=False)
            optimizer.step()
            if total_batch % 100 == 0: #每多少次输出在训练集和校验集上的效果
                true = labels.data.cpu()
                predit = torch.max(outputs.data, 1)[1].cpu()
                train_acc = metrics.accuracy_score(true, predit)
                dev_acc, dev_loss = evaluate(config, model, dev_iter)
                if dev_loss < dev_best_loss:
                    dev_best_loss = dev_loss
                    torch.save(model.state_dict(), config.save_path)
                    imporve = '*'
                    last_imporve = total_batch
                else:
                    imporve = ''
                time_dif = utils.get_time_dif(start_time)
                msg = 'Iter:{0:>6}, Train Loss:{1:>5.5}, Train Acc:{2:>6.5}, Val Loss:{3:>5.5}, Val Acc:{4:>6.5%}, Time:{5} {6}'
                print(msg.format(total_batch, loss.item(), train_acc, dev_loss, dev_acc, time_dif, imporve))
                model.train()
            total_batch = total_batch + 1
            if total_batch - last_imporve > config.require_improvement:
                #在验证集合上loss超过1000batch没有下降，结束训练
                print('在校验数据集合上已经很长时间没有提升了，模型自动停止训练')
                flag = True
                break

        if flag:
            break
    test(config, model, test_iter)

def evaluate(config, model, dev_iter, test=False):
    """

    :param config:
    :param model:
    :param dev_iter:
    :return:
    """
    model.eval()
    loss_total = 0
    predict_all = np.array([], dtype=int)
    labels_all = np.array([], dtype=int)
    with torch.no_grad():
        #text(数据[128,32] 真实长度[128] mask[128,32])
        for texts, labels in dev_iter:
            outputs = model(texts)
            loss = F.cross_entropy(outputs, labels)
            loss_total = loss_total + loss
            labels = labels.data.cpu().numpy()
            predict = torch.max(outputs.data,1)[1].cpu().numpy()
            labels_all = np.append(labels_all, labels)
            predict_all = np.append(predict_all, predict)

    acc = metrics.accuracy_score(labels_all, predict_all)
    if test:
        report = metrics.classification_report(labels_all, predict_all, target_names=config.class_list, digits=4)
        confusion = metrics.confusion_matrix(labels_all, predict_all)
        return acc, loss_total / len(dev_iter), report, confusion

    return acc, loss_total / len(dev_iter)

def test(config, model, test_iter):
    """
    模型测试
    :param config:
    :param model:
    :param test_iter:
    :return:
    """
    model.load_state_dict(torch.load(config.save_path))
    model.eval()
    start_time = time.time()

    #hook降维后的数据(128,768)
    # features_in_hook = torch.zeros((128,10),device='cuda:0')
    #
    # def hook(module, fea_in, fea_out):
    #     nonlocal features_in_hook
    #     # fea_in[0]是因为中间层输出变成了只有一个张量的元组，把张量取出来，我也不知道为什么是元组
    #     features_in_hook = torch.cat((features_in_hook,fea_in[0]),0)
    #     return None
    #
    # model.hooklayer.register_forward_hook(hook)

    #hook句子的词嵌入向量打平后的结果
    # features_in_hook = torch.zeros((128, 32*768), device='cuda:0')
    #
    # def hook(module, fea_in, fea_out):
    #     nonlocal features_in_hook
    #     # fea_in[0]是因为中间层输出变成了只有一个张量的元组，把张量取出来，我也不知道为什么是元组
    #     features_in_hook = torch.cat((features_in_hook, fea_in[0]), 0)
    #     return None
    #
    # model.f1.register_forward_hook(hook)

    #hook最终输出结果（送入softmax之前的数据）
    # features_in_hook = torch.zeros((128,10),device='cuda:0')
    #
    # def hook(module, fea_in, fea_out):
    #     nonlocal features_in_hook
    #     # 当hook的输出时，类型为张量，不再是装着张量的元组
    #     features_in_hook = torch.cat((features_in_hook,fea_out),0)
    #     return None
    #
    # model.hooklayer.register_forward_hook(hook)

    test_acc, test_loss ,test_report, test_confusion = evaluate(config, model, test_iter, test = True)

    # torch.save(features_in_hook, config.model_name+'10.pkl')

    msg = 'Test Loss:{0:>5.2}, Test Acc:{1:>6.2%}'
    print(msg.format(test_loss, test_acc))
    print("Precision, Recall and F1-Score")
    print(test_report)
    print("Confusion Maxtrix")
    print(test_confusion)
    time_dif = utils.get_time_dif(start_time)
    print("使用时间：",time_dif)



















