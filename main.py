import numpy as np
import tensorflow as tf
import argparse

import pommerman
from pommerman import agents

from utils import *
from transformer import *
from model import *
from shaping import *

parser = argparse.ArgumentParser(description='ma-graph')
parser.add_argument('--seed', type=int, default=1, metavar='S',
                    help='random seed (default: 1)')
# parser.add_argument('--num-processes', type=int, default=4, metavar='N',
#                     help='how many training processes to use (default: 4)')
parser.add_argument('--num-steps', type=int, default=20, metavar='NS',
                    help='number of forward steps in ma-graph (default: 20)')
parser.add_argument('--max-episode-length', type=int, default=10000, metavar='M',
                    help='maximum length of an episode (default: 10000)')
parser.add_argument('--env-name', default='PommeFFACompetition-v0', metavar='ENV',
                    help='environment to train on (default: PommeFFACompetition-v0)')
parser.add_argument('--display', default=False, metavar='D',
                    help='display the training environment.')
# parser.add_argument('--no-shared', default=False, metavar='O',
#                     help='use an optimizer without shared momentum.')
# ####################
# parser.add_argument('--eta', type=float, default=0.01, metavar='LR',
#                     help='scaling factor for intrinsic reward')
# parser.add_argument('--beta', type=float, default=0.2, metavar='LR',
#                     help='balance between inverse & forward')
# parser.add_argument('--lmbda', type=float, default=0.1, metavar='LR',
#                     help='lambda : balance between A3C & icm')

parser.add_argument('--outdir', default="./output", help='Output log directory')
# parser.add_argument('--record', action='store_true', help="Record the policy running video")

def main():

	# Print all possible environments in the Pommerman registry
	# print(pommerman.registry)
	sess = tf.Session()
	#sess = tf_debug.TensorBoardDebugWrapperSession(sess, 'localhost:6064')

	# Create a set of agents (exactly four)
	agent_list = [
	    agents.SimpleAgent(),
	    agents.SimpleAgent(),
	    agents.RandomAgent(),
	    agents.RandomAgent(),
	    # agents.DockerAgent("pommerman/simple-agent", port=12345),
	]
	env = pommerman.make(args.env_name, agent_list)


	# Create the Estimator
	estimator_nn1 = tf.estimator.Estimator(model_fn=model_NN1, model_dir=args.outdir + '/sa_nn1')
	# Set up logging for predictions
	tensors_to_logNN1 = {"probabilities": "softmax_tensor"}
	logging_hook_nn1 = tf.train.LoggingTensorHook(tensors=tensors_to_logNN1, every_n_iter=50)

	# Create the Estimator
	estimator_nn2 = tf.estimator.Estimator(model_fn=model_NN2, model_dir=args.outdir + '/sa_nn2')
	# Set up logging for predictions
	tensors_to_logNN2 = {"probabilities": "softmax_tensor"}
	logging_hook_nn2 = tf.train.LoggingTensorHook(tensors=tensors_to_logNN2, every_n_iter=50)

	r_sum = np.zeros(1)
	
	for i in range(args.num_steps):
	    # Make the "Free-For-All" environment using the agent list
	    env.reset()
	    # Run the episodes just like OpenAI Gym
	    for i_episode in range(args.max_episode_length):
	        state = env.reset()
	        
	        done = False
	        curr_state = None
	        prev_state = None
	        graph = np.random.rand(4, 120).astype("float32") + 0.0001
	#         print(graph)
	        pr_action = None
	        pr_pr_action = None
	        
	        while not done:

	            if args.display:
	                env.render()

	            actions = env.act(state)
	            state, reward, done, info = env.step(actions)
	            r_sum[i] += reward[0]
	            
	            # as basic implementation I consider only one agent
	            prev_state = curr_state
	            curr_state = state

	            if pr_pr_action is not None:
	                # Train the model
	                for agent_num in range(4):

	                    curr_state_matrix = np.resize(state_to_matrix_with_action(curr_state[agent_num], action=pr_action[agent_num]).astype("float32"), (1, 38 * 11))
	                    prev_state_matrix = np.resize(state_to_matrix_with_action(prev_state[agent_num],action=pr_pr_action[agent_num]).astype("float32"), (1, 38 * 11))
	                    
	                    reward_shaping(graph, curr_state_matrix, prev_state_matrix, agent_num)

	                    train_input_NN2 = tf.estimator.inputs.numpy_input_fn(
	                        x={"state": curr_state_matrix,
	                           "graph": np.resize(graph, (1, 4*120))},
	                        y=np.asarray([actions[agent_num]]),
	                        batch_size=1,
	                        num_epochs=None,
	                        shuffle=True)

	                    train_input_NN1 = tf.estimator.inputs.numpy_input_fn(
	                        x={"state1": prev_state_matrix,
	                           "state2": curr_state_matrix},
	                        y=np.asmatrix(graph.flatten()),
	                        batch_size=1,
	                        num_epochs=None,
	                        shuffle=True)
	                    # estimator_nn1.train(
	                    #     input_fn=train_input_NN1,
	                    #     steps=200,
	                    #     hooks=[logging_hook_nn1])

	                    # estimator_nn2.train(
	                    #     input_fn=train_input_NN2,
	                    #     steps=200,
	                    #     hooks=[logging_hook_nn2])
	                    # predictions = estimator_nn2.predict(input_fn=train_input_NN2)
	                    # next_action = np.array(list(p['classes'] for p in predictions))
	                    
	            pr_pr_action = pr_action
	            pr_action = actions
	            
	        if i_episode > 300:
	            break
	            
	    print('Game {} finished'.format(i))

	np.savetxt(args.outdir + '/result_2simple_2random.csv', r_sum, fmt='%1.4e')
	env.close()


if __name__ == '__main__':
    args = parser.parse_args()

    tf.set_random_seed(args.seed)
    np.random.seed(args.seed)

    main()
