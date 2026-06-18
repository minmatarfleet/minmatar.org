const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

config.resolver.assetExts.push('woff', 'woff2');

// react-native-svg's package.json "react-native" field points at TypeScript source,
// which breaks Metro resolution for internal imports like ./utils/fetchData.
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === 'react-native-svg') {
    return {
      filePath: path.resolve(
        context.projectRoot,
        'node_modules/react-native-svg/lib/commonjs/index.js',
      ),
      type: 'sourceFile',
    };
  }

  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
