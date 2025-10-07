#include "heap.h"
#include <stdlib.h>
#include <stdio.h>

char isEmpty(struct heap* h){
    return h->size == 0;
}

void initHeap(struct heap* h, int (*compare)(void*, void*)){
    h->heapData = (void**)malloc(sizeof(void*)*10);
    h->size = 0;
    h->capacity = 10;
    h->compare = compare;
}

void resize(struct heap* h){
    // make a new array with double the size
    void** newHeap = (void**)malloc(sizeof(void*)*h->capacity*2);
    // copy the data from the old array to the new array
    for(int i = 0; i < h->size; i++){
        newHeap[i] = h->heapData[i];
    }
    // free the old array
    free(h->heapData);
    // update the heap
    h->heapData = newHeap;
    h->capacity *= 2;
}

void insert(struct heap* h, void* data){
    // make a new heapNode with the data
    // need to reallocate the array before entrey, for this case assume the heap is already big enougth
    h->heapData[h->size] = data; // the pointer to the data is stored in the heap
    int index = h->size; // the index of the new node
    h->size++; // increase the size of the heap
    if (h->size == h->capacity){
        resize(h);
    }
    // now we need to fix the heap
    while(index > 0 && h->compare(h->heapData[index], h->heapData[(index-1)/2]) > 0){
        // swap the two nodes
        void* temp = h->heapData[index];
        h->heapData[index] = h->heapData[(index-1)/2];
        h->heapData[(index-1)/2] = temp;
        // update the index
        index = (index-1)/2;
    }
    // now the heap may not be in order, so we need to fix it
}

void* removeMax(struct heap* h){
    // get the max value
    void* max = h->heapData[0];
    // move the last element to the top
    h->heapData[0] = h->heapData[h->size-1];
    h->size--;
    // now we need to fix the heap
    int index = 0;
    while(2*index+1 < h->size){
        int left = 2*index+1;
        int right = 2*index+2;
        int swapIndex = left;
        if (right < h->size && h->compare(h->heapData[right], h->heapData[left]) > 0){
            swapIndex = right;
        }
        if (h->compare(h->heapData[swapIndex], h->heapData[index]) > 0){
            void* temp = h->heapData[index];
            h->heapData[index] = h->heapData[swapIndex];
            h->heapData[swapIndex] = temp;
            index = swapIndex;
        } else {
            break;
        }
    }
    return max;
}
