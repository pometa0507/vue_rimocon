<template>
  <v-container>
    <v-row class="text-center">
      <v-col cols="12">
        <v-img
          :src="require('../assets/logo.svg')"
          class="my-3"
          contain
          height="200"
        />
      </v-col>

      <v-col class="mb-4">
        <h1 class="display-2 font-weight-bold mb-3">
          Welcome to Vuetify
        </h1>

      <div>
        <input @click="testGet" type="button" value="Test GET">
        <input @click="testPost" type="button" value="Test POST">
        <input @click="testPostData" type="button" value="Test POSTData">
      </div>

      <div>
        <input @click="sendCmd1" type="button" value="Test CmdData1">
        <input @click="sendCmd2" type="button" value="Test CmdData2">
      </div>

      </v-col>

    </v-row>
  </v-container>
</template>

<script>
  export default {
    name: 'rimocon',

    data: () => ({
 
      
    }),

    methods: {
      testGet() {
        this.axios.get('/check_method')
          .then((response) => {
            alert(response.data);
          })
          .catch((e) => {
            alert(e);
          });
      },
      testPost() {
        this.axios.post('/check_method')
          .then((response) => {
            alert(response.data);
          })
          .catch((e) => {
            alert(e);
          });
      },

      testPostData() {
        this.axios.post('/take_post', {
            firstName: 'pome',
            lastName: 'ranny'
          })
          .then((response) => {
            alert(response.data);
          })
          .catch((e) => {
            alert(e);
          })
      },

      sendCmd1() {
        this.axios.post('/send_cmd', {
            cmd: 'LivingLightDown'
          })
          .then((response) => {
            alert(response.data);
          })
          .catch((e) => {
            alert(e);
          })
      },
      sendCmd2() {
        this.axios.post('/send_cmd', {
            cmd: 'LivingLightOn'
          })
          .then((response) => {
            alert(response.data);
          })
          .catch((e) => {
            alert(e);
          })
      },
    }
  }
</script>
