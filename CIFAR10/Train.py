import argparse
import sys
import os
import math
import time
from six.moves import xrange
import tensorflow as tf

import Model as model
import InputHandler as inputHandler

FLAGS = None

def train():
    """

    """
    with tf.name_scope("training"):
        X,y = model.placeholders()
        logits = model.inference(X)
        Xentropy = tf.nn.sparse_softmax_cross_entropy_with_logits(
            logits=logits,
            labels=y
        )
        loss = tf.reduce_mean(Xentropy)

        # Add this to TensorBoard
        tf.summary.scalar('loss', loss)

        optimizer = tf.train.AdamOptimizer()
        train_op = optimizer.minimize(loss)

        # Evaluation metric
        predictions = tf.nn.in_top_k(logits, y, 1)
        accuracy = tf.reduce_mean(tf.cast(predictions, tf.float32))

        # Add this to TensorBoard
        tf.summary.scalar('accuracy', accuracy)

    filename_queue = inputHandler.get_filenames_queue(
        data_dir=FLAGS.data_dir,
        epochs=FLAGS.epochs,
        is_train=True)

    with tf.device('/cpu:0'):
        image_batch_op, label_batch_op = inputHandler.get_data_batch(
                                        filename_queue,
                                        batch_size=FLAGS.batch_size,
                                        is_train=True,
                                        shuffle=True,
                                        augmented=True)

    merged = tf.summary.merge_all()
    train_writer = tf.summary.FileWriter(FLAGS.log_dir, tf.get_default_graph())

    init = tf.group(tf.global_variables_initializer(),
               tf.local_variables_initializer())
    with tf.Session() as sess:
        # Continue from previously trained model?
        if FLAGS.retrain:
            print(sess.run(tf.report_uninitialized_variables()))
            saver = tf.train.Saver()
            ckpt = tf.train.get_checkpoint_state(FLAGS.ckpt_dir)
            if ckpt and ckpt.model_checkpoint_path:
                # Restores from checkpoint
                saver.restore(sess, ckpt.model_checkpoint_path)
            else:
                print('No checkpoint file found')
                return
            print(sess.run(tf.report_uninitialized_variables()))
        else:
            sess.run(init)

        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(coord=coord)
        steps = int(math.ceil(inputHandler.NUM_EXAMPLES_PER_EPOCH_FOR_TRAIN/FLAGS.batch_size))
        train_steps = int(steps * 0.8)
        val_steps = int(steps * 0.2)
        epoch = 0
        try:
            while (not coord.should_stop()) and (epoch < FLAGS.epochs):
                # Using random cross validation.
                # i.e While shuffling the data, in each epoch,
                # 80% is used for training,
                # and the rest is used to evaluate.

                start_time = time.time()

                # Training batches
                for i in xrange(train_steps):
                    image_batch, label_batch = sess.run([image_batch_op, label_batch_op])
                    summary,_, loss_value = sess.run([merged, train_op, loss],
                        feed_dict={
                            X: image_batch,
                            y: label_batch
                        }
                    )
                # Validation batches
                for i in xrange(val_steps):
                    image_batch, label_batch = sess.run([image_batch_op, label_batch_op])
                    summary,train_accuracy = sess.run([merged, accuracy],
                        feed_dict={
                            X: image_batch,
                            y: label_batch
                        }
                    )

                # End of epoch, Calculate duration in seconds
                duration = time.time() - start_time

                epoch += 1
                train_writer.add_summary(summary, epoch)
                print("Epoch: {0}, Loss: {1}, Training Accuracy: {2}, Duration: {3}(s)"
                        .format(epoch, loss_value, train_accuracy, duration))

        except tf.errors.OutOfRangeError:
            print('Done training -- epoch limit reached')
        train_writer.close()
        coord.request_stop()
        coord.join(threads)

        checkpoint_file = os.path.join(FLAGS.ckpt_dir, 'model.ckpt')
        saver = tf.train.Saver()
        saver.save(sess, checkpoint_file)
        sess.close()

def main(_):
    # Clear graph
    tf.reset_default_graph()
    # Delete existing directories
    inputHandler.delete_directories(FLAGS.log_dir)
    if not FLAGS.retrain:
        inputHandler.delete_directories(FLAGS.ckpt_dir)
    train()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("--batch_size", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument(
        "--ckpt_dir",
        type=str,
        default="/home/kbanala/Work/DataScience/Projects-ML-DL/CIFAR10/checkpoints",
        help="directory to store checkpoints")
    parser.add_argument(
        "--data_dir",
        type=str,
        default="/home/kbanala/Work/DataScience/DataSets/CIFAR10/cifar-10-batches-bin",
        help='directory for datasets.')
    parser.add_argument(
        '--log_dir',
        type=str,
        default="/tmp/tf/CIFAR10/train",
        help='Summaries log directory')
    parser.add_argument(
        '--retrain',
        type=bool,
        default=False,
        help="Continue from previously trained weights."
    )
    FLAGS, unparsed = parser.parse_known_args()
    tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
