import math
from collections import Counter

'''The main method in this module makes multiple evaluations of Katz back-off using different discount values.'''

# start symbol
START = '<s>'
# stop symbol
STOP = '</s>'
# unk symbol
UNK = '<UNK>'
# the names of the different datasets we want to model
DATASETS = ['reuters', 'brown', 'gutenberg']
# whether or not to evaluate on the dev datasets
DEV = True


def main():
    KATZ_DISCOUNTS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    def get_log_prob(n_gram, model, trie_dicts, caches):
        prob = get_prob(n_gram, model, trie_dicts, caches)
        log_prob = math.log(prob, 2)
        return log_prob

    # returns the probability of a specified n-gram in the model
    def get_prob(n_gram, model, trie_dicts, caches):

        # in the case that we've calculated this probability before
        if n_gram in caches[0]:
            return caches[0][n_gram]

        # if we're trying to find the probability of the empty sequence, it's just 0
        # honestly, this shouldn't happen and if it does, something has gone wrong
        if len(n_gram) == 0:
            print('CALLED GET PROB WITH SEQUENCE LENGTH OF 0')
            print('THIS SHOULD NOT HAVE HAPPENED')
            return 0

        # if our n-gram appeared in our training data, that means we can just go grab the MLE
        # also, if our n-gram is a uni-gram, we can just go grab it's probability
        # if n_gram_seen_in_training(n_gram, model) or len(n_gram) == 1:
        if len(n_gram) == 1 or n_gram in model[len(n_gram) - 1]:
            prob = get_discounted_MLE_prob(n_gram, model)
            return prob

        # here, we need to perform the back-off
        next_gram = n_gram[1:]
        history_n_gram = n_gram[:-1]
        numer = get_prob(next_gram, model, trie_dicts, caches)
        denom = get_backoff_denom(history_n_gram, model, trie_dicts, caches)
        alpha = get_alpha(history_n_gram, model, trie_dicts, caches)

        prob = alpha * numer / denom
        caches[0][n_gram] = prob

        return prob

    def get_discounted_MLE_prob(n_gram, model):
        if len(n_gram) == 1:
            numer = model[0][n_gram]
            denom = sum(model[0].values()) - model[0][(START,)]
        else:
            numer = model[len(n_gram) - 1][n_gram] - KATZ_DISCOUNT
            denom = model[len(n_gram) - 2][n_gram[:-1]]

        return numer / denom

    def get_backoff_denom(history_n_gram, model, trie_dicts, caches):
        if history_n_gram in caches[2]:
            return caches[2][history_n_gram]

        if len(history_n_gram) == 1:
            curr_sum = 0
            for word, count in trie_dicts[0][history_n_gram].items():
                curr_sum += get_discounted_MLE_prob((history_n_gram[-1], word), model)

            caches[2][history_n_gram] = 1 - curr_sum
            return 1 - curr_sum

        if len(history_n_gram) == 2:
            curr_sum = 0
            if history_n_gram in trie_dicts[1]:
                for word, count in trie_dicts[1][history_n_gram].items():
                    curr_sum += get_discounted_MLE_prob((history_n_gram[-1], word), model)

            caches[2][history_n_gram] = 1 - curr_sum
            return 1 - curr_sum

    def get_alpha(history_n_gram, model, trie_dicts, caches):
        if history_n_gram in caches[1]:
            return caches[1][history_n_gram]

        ret = 0
        if len(history_n_gram) == 2:
            if history_n_gram in trie_dicts[1]:
                for word, count in trie_dicts[1][history_n_gram].items():
                    ret += (count - KATZ_DISCOUNT) / model[1][history_n_gram]

            ret = 1 - ret

        if len(history_n_gram) == 1:
            ret = 0
            for word, count in trie_dicts[0][history_n_gram].items():
                ret += (count - KATZ_DISCOUNT) / model[0][history_n_gram]

            ret = 1 - ret

        caches[1][history_n_gram] = ret
        return ret

    KATZ_DISCOUNT = None
    for i in KATZ_DISCOUNTS:
        KATZ_DISCOUNT = i
        for train_dataset in DATASETS:
            print('training on ' + train_dataset + '...')
            unigrams, bigrams, trigrams, unigrams_to_words_to_counts, bigrams_to_words_to_counts = train(
                'data/' + train_dataset + '_train.txt')
            model = (unigrams, bigrams, trigrams)
            trie_dicts = (unigrams_to_words_to_counts, bigrams_to_words_to_counts)

            # (n_grams_to_probs, history_to_alphas, history_to_denoms)
            caches = (dict(), dict(), dict())

            print('using Katz discount of: ' + str(KATZ_DISCOUNT))
            for test_dataset in DATASETS:
                print('evaluating ' + train_dataset + ' on ' + test_dataset + ' test set...')
                if DEV:
                    perplexity = eval_model('data/' + test_dataset + '_dev.txt', model, get_log_prob, trie_dicts,
                                            caches)
                else:
                    perplexity = eval_model('data/' + test_dataset + '_test.txt', model, get_log_prob, trie_dicts,
                                            caches)

                print('trained on: ' + train_dataset + '; tested on: ' + test_dataset + '; perplexity: ' + str(
                    perplexity))


def eval_model(filename, model, log_prob_func, dict_tries, caches):
    log_prob_sum = 0
    file_word_count = 0

    with open(filename, encoding='iso-8859-1') as f:
        for line in f:
            log_prob, num_tokens = eval_sentence(line, model, log_prob_func, dict_tries, caches)
            log_prob_sum += log_prob
            file_word_count += num_tokens
        f.close()

    average_log_prob = log_prob_sum / file_word_count
    perplexity = 2 ** (-average_log_prob)
    return perplexity


# returns log probability of a sentence and how many tokens were in the sentence
def eval_sentence(sentence, model, log_prob_func, trie_dicts, caches):
    tokens = [token if (token,) in model[0] else UNK for token in sentence.split()]
    num_tokens = len(tokens) + 1
    tokens.insert(0, START)
    tokens.insert(0, START)
    tokens.append(STOP)

    log_prob_sum = 0
    for i in range(len(tokens) - 2):
        n_gram = tuple(tokens[i:i + 3])
        next_prob = log_prob_func(n_gram, model, trie_dicts, caches)
        log_prob_sum += next_prob

    return log_prob_sum, num_tokens


def train(filename):
    # initializing empty Counter objects to store the n-grams
    unigrams = Counter()
    bigrams = Counter()
    trigrams = Counter()
    bigrams_to_w_to_counts = dict()
    unigrams_to_w_to_counts = dict()

    lines = list()
    with open(filename, encoding='iso-8859-1') as f:
        for line in f:
            lines.append(line)

    # creating the unigram counts
    for line in lines:
        tokens = line.split()
        tokens.insert(0, START)
        tokens.insert(0, START)
        tokens.append(STOP)
        add_n_gram_counts(1, unigrams, tokens, None)

    # the set of all words that have a count of 1
    unks = set()
    for unigram, count in unigrams.items():
        if count == 1:
            unks.add(unigram[0])

    for word in unks:
        del unigrams[(word,)]

    unigrams[(UNK,)] = len(unks)

    # creating the bigram and trigram counts
    for line in lines:
        tokens = [token if token not in unks else UNK for token in line.split()]
        tokens.insert(0, START)
        tokens.insert(0, START)
        tokens.append(STOP)
        add_n_gram_counts(2, bigrams, tokens, unigrams_to_w_to_counts)
        add_n_gram_counts(3, trigrams, tokens, bigrams_to_w_to_counts)

    return unigrams, bigrams, trigrams, unigrams_to_w_to_counts, bigrams_to_w_to_counts


# adds the n-grams to the specified Counter from the specified tokens
def add_n_gram_counts(n, n_grams, tokens, cache):
    for i in range(len(tokens) - (n - 1)):
        n_gram = tuple(tokens[i:i + n])
        n_grams[n_gram] += 1

        if n > 1:
            if n_gram[:-1] not in cache:
                cache[n_gram[:-1]] = Counter()
            cache[n_gram[:-1]][n_gram[-1]] += 1

    return n_grams


if __name__ == '__main__':
    main()
from linear_interpolation import train
from linear_interpolation import eval_model


